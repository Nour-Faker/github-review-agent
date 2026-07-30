import asyncio
import httpx
from app.diff_extractor import DiffExtractor
from app.llm_analyzer import LLMAnalyzer
from app.commenter import GitHubCommenter
from app.rate_limiter import RateLimiter
from app.config import settings

REPO = "Nour-Faker/github-review-agent"
PR_NUMBER = 1

async def get_commit_sha(repo: str, pr_number: int) -> str:
    """Récupère le vrai commit SHA de la PR."""
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    headers = {
        "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
    return response.json()["head"]["sha"]

async def test_pipeline():
    print("=" * 50)
    print("TEST PIPELINE — GitHub Review Agent")
    print("=" * 50)

    print("\n[1] Extraction du diff...")
    extractor = DiffExtractor()
    try:
        diff = await extractor.fetch_diff(REPO, PR_NUMBER)
        print(f"    ✅ Diff récupéré — {len(diff.split(chr(10)))} lignes")
    except Exception as e:
        print(f"    ❌ Erreur: {e}")
        return

    print("\n[2] Vérification taille...")
    if extractor.is_oversized(diff):
        print(f"    ❌ Diff > 500 lignes")
        return
    print(f"    ✅ Taille OK")

    print("\n[3] Parsing hunks...")
    hunks = extractor.parse_hunks(diff)
    print(f"    ✅ {len(hunks)} fichiers")
    for h in hunks:
        print(f"       → {h.file}")

    print("\n[4] Récupération commit SHA...")
    commit_sha = await get_commit_sha(REPO, PR_NUMBER)
    print(f"    ✅ SHA: {commit_sha[:10]}...")

    print("\n[5] Analyse LLM...")
    analyzer = LLMAnalyzer()
    limiter = RateLimiter()
    results = []
    for hunk in hunks:
        limiter.check_and_wait_retry()
        print(f"    → Analyse {hunk.file}...")
        result = analyzer.analyze_hunk(hunk)
        print(f"       ✅ {result.comment[:80]}...")
        results.append((hunk, result))

    print("\n[6] Publication commentaires...")
    commenter = GitHubCommenter()
    await commenter.post_review(
        results=results,
        repo=REPO,
        pr_number=PR_NUMBER,
        commit_sha=commit_sha
    )

    print("\n" + "=" * 50)
    print("✅ PIPELINE COMPLET — Sprint 3 validé !")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(test_pipeline())