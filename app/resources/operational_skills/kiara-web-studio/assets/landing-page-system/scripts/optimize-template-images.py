from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1] / "templates"
PREFIXES = ("advogado-template-", "beleza-template-", "dentista-template-", "educador-fisico-template-", "nutricionista-template-", "psicologo-template-", "personal-trainer")
converted = 0
before = 0
after = 0

for template in (path for path in ROOT.iterdir() if path.is_dir() and path.name.startswith(PREFIXES)):
    html_path = template / "index.html"
    html = html_path.read_text(encoding="utf-8")
    for source in template.rglob("*.png"):
        target = source.with_suffix(".webp")
        before += source.stat().st_size
        with Image.open(source) as image:
            image.save(target, "WEBP", quality=84, method=6, lossless=image.mode in ("RGBA", "LA"))
        relative_source = source.relative_to(template).as_posix()
        relative_target = target.relative_to(template).as_posix()
        html = html.replace(relative_source, relative_target)
        after += target.stat().st_size
        source.unlink()
        converted += 1
    html_path.write_text(html, encoding="utf-8")

print(f"Converted {converted} PNG files to WebP: {before / 1048576:.1f} MB -> {after / 1048576:.1f} MB")
