import base64
import logging
import aiohttp

from config import GITHUB_TOKEN, GITHUB_REPO, GITHUB_BACKUP_BRANCH

logger = logging.getLogger(__name__)

API_BASE = "https://api.github.com"
DB_FILE_PATH_IN_REPO = "bot.db"


def _headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }


def _configured() -> bool:
    return bool(GITHUB_TOKEN and GITHUB_REPO)


async def _ensure_branch_exists(session: aiohttp.ClientSession):
    url = f"{API_BASE}/repos/{GITHUB_REPO}/branches/{GITHUB_BACKUP_BRANCH}"
    async with session.get(url, headers=_headers()) as resp:
        if resp.status == 200:
            return

    url_ref = f"{API_BASE}/repos/{GITHUB_REPO}/git/ref/heads/main"
    async with session.get(url_ref, headers=_headers()) as resp:
        if resp.status != 200:
            logger.warning("Could not read main branch ref to create backup branch")
            return
        data = await resp.json()
        sha = data["object"]["sha"]

    url_create = f"{API_BASE}/repos/{GITHUB_REPO}/git/refs"
    payload = {"ref": f"refs/heads/{GITHUB_BACKUP_BRANCH}", "sha": sha}
    async with session.post(url_create, headers=_headers(), json=payload) as resp:
        if resp.status not in (200, 201):
            logger.warning("Could not create backup branch: %s", await resp.text())


async def restore_from_github(db_path: str):
    if not _configured():
        logger.info("GitHub backup not configured, skipping restore")
        return
    url = f"{API_BASE}/repos/{GITHUB_REPO}/contents/{DB_FILE_PATH_IN_REPO}?ref={GITHUB_BACKUP_BRANCH}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=_headers()) as resp:
                if resp.status != 200:
                    logger.info("No existing backup found on GitHub (status %s)", resp.status)
                    return
                data = await resp.json()
                raw = base64.b64decode(data.get("content", ""))
                with open(db_path, "wb") as f:
                    f.write(raw)
                logger.info("Restored database from GitHub backup branch '%s'", GITHUB_BACKUP_BRANCH)
    except Exception as exc:
        logger.warning("Failed to restore database from GitHub: %s", exc)


async def backup_to_github(db_path: str):
    if not _configured():
        return
    import os
    if not os.path.exists(db_path):
        return

    with open(db_path, "rb") as f:
        raw = f.read()
    content_b64 = base64.b64encode(raw).decode()
    url = f"{API_BASE}/repos/{GITHUB_REPO}/contents/{DB_FILE_PATH_IN_REPO}"

    try:
        async with aiohttp.ClientSession() as session:
            await _ensure_branch_exists(session)

            sha = None
            get_url = f"{url}?ref={GITHUB_BACKUP_BRANCH}"
            async with session.get(get_url, headers=_headers()) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    sha = data.get("sha")

            payload = {
                "message": "Auto-backup: qw1zo shop bot database",
                "content": content_b64,
                "branch": GITHUB_BACKUP_BRANCH,
            }
            if sha:
                payload["sha"] = sha

            async with session.put(url, headers=_headers(), json=payload) as resp:
                if resp.status not in (200, 201):
                    logger.warning("GitHub backup failed: %s", await resp.text())
                else:
                    logger.info("Database backed up to GitHub branch '%s'", GITHUB_BACKUP_BRANCH)
    except Exception as exc:
        logger.warning("Failed to backup database to GitHub: %s", exc)
