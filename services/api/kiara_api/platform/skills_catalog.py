"""Metadata-only skill catalog bundled with the standalone API deployment."""

SKILLS_CATALOG = (
    {
        "name": "ig-audit",
        "description": 'Post-mortem on what the user has already posted - which reels actually worked, why, and what to stop making. Use when the user pastes their Instagram insights or past posts and asks "what\'s working", "why did this flop", "read my analytics", "audit my content", or wants to know what to do more of.',
    },
    {
        "name": "ig-caption",
        "description": 'Write the Instagram caption - the line that survives the "... more" cut, the body, the single ask, the search terms and the three hashtags - and lint it before it goes out. Use when the user says "write the caption", "caption this", "what do I put in the description", has a reel or a carousel ready and needs the text, or asks about hashtags.',
    },
    {
        "name": "ig-carousel",
        "description": 'Build an Instagram carousel - the cover that earns the swipe, slide-by-slide copy, and the 1080x1350 files to upload. Use when the user says "carousel", "slides", "swipe post", "turn this into a carousel", or has a list-shaped or step-shaped idea that would die as a single image.',
    },
    {
        "name": "ig-comment",
        "description": 'Write comments on other people\'s Instagram posts and reels that read as a person with an opinion, not a bot. Use when the user pastes a post or a reel and wants a comment, says "comment on this", "engage with this", "what do I say here", or wants a batch for their daily engagement round.',
    },
    {
        "name": "ig-dm",
        "description": 'Write Instagram DMs that get replies - the keyword delivery, the first message to someone who engaged, the collab pitch, and the two follow-ups. Use when the user says "DM this person", "what do I send them", "outreach message", "how do I follow up", "pitch this brand", or is reaching out to someone specific.',
    },
    {
        "name": "ig-human",
        "description": 'Strip the machine fingerprint out of any draft - em dashes, AI slop words, invisible watermark characters - and score it against a five-check detection panel before it goes out. Use whenever text needs to sound human, when the user says humanize, "does this sound like AI", "remove the em dashes", "de-slop this", "this sounds like ChatGPT", or before any caption, script, comment, reply or DM is shown to the user.',
    },
    {
        "name": "ig-plan",
        "description": 'Build the week on Instagram - what to post, which format, when, and who to engage with. Use when the user says "plan my week", "what should I post", "content calendar", "I have nothing to post about", or wants a posting schedule and an engagement list.',
    },
    {
        "name": "ig-profile",
        "description": 'Score an Instagram profile out of 100 against a 12-part rubric and rewrite the parts that lose points - name field, bio, link, highlights, pinned three, grid. Use when the user says "optimize my profile", "fix my bio", "score my Instagram", "why don\'t people follow me", or pastes their profile and asks how it reads.',
    },
    {
        "name": "ig-reel",
        "description": 'Write an Instagram Reel from a raw idea - hook options off 26 formulas, the spoken script, the on-screen text, and a timed beat sheet - in the user\'s own voice and scored before they shoot it. Use whenever the user wants a Reel, a short-form video script, a hook, a voiceover, "make a reel about X", "what should I say in this video", or is about to record and does not have the first line yet.',
    },
    {
        "name": "ig-reply",
        "description": 'Handle the comments under the user\'s own reels and posts - draft replies to the ones worth answering, sorted by which ones are. Use when the user pastes their comments, says "reply to these", "handle my comments", "someone said X on my reel", or is dealing with a critic, a hater or a lead in the comments.',
    },
    {
        "name": "ig-repurpose",
        "description": 'Turn one long asset - a YouTube video, podcast, livestream, newsletter, blog post or client call - into a week of reels and carousels. Use when the user says "repurpose this", "turn this into reels", "I have a video/podcast/ transcript", "cut this up", or pastes something long and wants it on Instagram.',
    },
    {
        "name": "ig-story",
        "description": 'Write the day\'s Instagram Stories - the frame-by-frame sequence, which stickers to use where, and the one that moves people into the DMs. Use when the user says "stories", "what do I post on my story", "story sequence", "poll idea", "I have nothing to story about", or wants to sell something without making a post about it.',
    },
    {
        "name": "ig-viral",
        "description": 'Go and find the reels that are actually working right now in the user\'s niche, rank them by how far each beat its own account, name the hook formula each one used, and turn that into a swipe file they can shoot from. Use when the user says "find viral videos", "what\'s working right now", "what are people posting in my niche", "reverse engineer this account", "build me a swipe file", "why is this reel doing numbers", or asks what to make next and has no evidence to answer with.',
    },
    {
        "name": "google-maps-scraper",
        "description": 'Find businesses, leads, emails, reviews, ratings, and contact details from Google Maps. Use for requests such as "find dentists in Berlin", "scrape Google Maps", "get local business leads", or "collect Google Maps reviews". Runs the open-source scraper locally with Docker and guides nontechnical users through setup, monitoring, and results.\n',
    },
    {
        "name": "kiara-chatwoot",
        "description": "Consultar caixas de entrada e conversas de atendimento no Chatwoot e preparar respostas confirmadas aos clientes pela Kiara.",
    },
    {
        "name": "kiara-freellmapi",
        "description": "Configurar e operar o roteador FreeLLMAPI da Kiara, selecionar modelos e diagnosticar falhas de inferencia nesse provider.",
    },
    {
        "name": "kiara-video-studio",
        "description": 'Produzir vídeos de apresentação e venda narrados pela própria Kiara (orbe animado com voz), com telas reais do sistema, cards sincronizados com a fala, saudação personalizada com o nome dos clientes e efeitos 3D.',
    },
    {
        "name": "kiara-web-studio",
        "description": 'Criar sites e landing pages a partir do acervo Landing Page System da Kiara: 33 templates profissionais, brief, design premium, critérios de qualidade, mídia cinematográfica e preparação de preview/publicação.',
    },
)
