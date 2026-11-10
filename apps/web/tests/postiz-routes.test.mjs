import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import ts from "typescript";
import { fileURLToPath } from "node:url";
const root=fileURLToPath(new URL("../src", import.meta.url));
function route(file, {denied=null, upstream=async()=>[]}={}) {
  const calls=[];
  class PostizRequestError extends Error { constructor(message,status,code){super(message);this.status=status;this.code=code;} }
  const mocks={
    "@/lib/postiz/admin":{requireContentAdmin:async()=>denied},
    "@/lib/postiz/client":{PostizRequestError,postizRequest:async(path,init)=>{calls.push({path,init});return upstream(path,init);},postizErrorResponse:(e)=>Response.json({error:{message:e.message}},{status:e.status||502})}
  };
  const cache=new Map();
  function load(path){
    if(cache.has(path))return cache.get(path);
    const result={};cache.set(path,result);
    const compiled=ts.transpileModule(readFileSync(path,"utf8"),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
    new Function("require","exports",compiled)((name)=>mocks[name]||load((name.startsWith("@/")?resolve(root,name.slice(2)):resolve(dirname(path),name))+".ts"),result);
    return result;
  }
  return {api:load(resolve(root,"app/api/content/postiz",file)),calls};
}
const input={type:"schedule",date:"2099-10-01T12:00:00Z",integrationId:"channel-one",provider:"threads",content:"Teste",media:[],settings:{}};
const request=(body)=>new Request("http://localhost/api/content/postiz/posts",{method:"POST",body:JSON.stringify(body)});
test("requires admin before calling Postiz",async()=>{
  const {api,calls}=route("posts/route.ts",{denied:new Response(null,{status:403})});
  assert.equal((await api.POST(request(input))).status,403);assert.equal(calls.length,0);
});
test("rejects invalid JSON without calling Postiz",async()=>{
  const {api,calls}=route("posts/route.ts");
  assert.equal((await api.POST(new Request("http://localhost",{method:"POST",body:"{"}))).status,422);assert.equal(calls.length,0);
});
test("prevents wrong provider and disabled channel from publishing",async()=>{
  for(const channel of [{id:"channel-one",identifier:"instagram"},{id:"channel-one",identifier:"threads",disabled:true}]){
    const {api,calls}=route("posts/route.ts",{upstream:async()=>[channel]});
    assert.ok([409,422].includes((await api.POST(request(input))).status));assert.equal(calls.length,1);
  }
});
test("sends scheduling payload only to a channel owned by configured account",async()=>{
  const {api,calls}=route("posts/route.ts",{upstream:async(path)=>path.endsWith("integrations")?[{id:"channel-one",identifier:"threads"}]:[{postId:"post-one"}]});
  assert.equal((await api.POST(request(input))).status,201);
  const sent=JSON.parse(calls[1].init.body);assert.equal(sent.type,"schedule");assert.equal(sent.posts[0].settings.__type,"threads");assert.equal(sent.posts[0].integration.id,"channel-one");
});
test("dashboard validates interval before upstream calls",async()=>{
  const {api,calls}=route("dashboard/route.ts");
  assert.equal((await api.GET(new Request("http://localhost?startDate=bad"))).status,422);assert.equal(calls.length,0);
});
test("deletion returns an empty response after upstream success",async()=>{
  const {api,calls}=route("posts/[postId]/route.ts");
  const result=await api.DELETE(new Request("http://localhost"),{params:Promise.resolve({postId:"post-one"})});
  assert.equal(result.status,204);assert.equal(await result.text(),"");assert.equal(calls[0].init.method,"DELETE");
});
test("unsupported upload is rejected before transmission",async()=>{
  const {api,calls}=route("upload/route.ts");
  const form=new FormData();form.set("file",new File(["x"],"test.html",{type:"text/html"}));
  assert.equal((await api.POST(new Request("http://localhost",{method:"POST",body:form}))).status,422);assert.equal(calls.length,0);
});
