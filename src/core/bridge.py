import asyncio
from concurrent.futures import ThreadPoolExecutor
from . import imap_client, smtp_client, storage_api, summariser

_executor = ThreadPoolExecutor(max_workers=4)

async def run_in_executor(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, func, *args)

## TODO: add bridge functions here

# fetch new emails, view inbox, view specific email, send email, delete email, summarise email, save as draft, view drafts, schedule email, view scheduled emails, search emails, filter emails, manage folders, flags, tags, download attachments, upload attachments, view attachments, delete attachments