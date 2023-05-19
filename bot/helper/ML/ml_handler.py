#!/usr/bin/env python3
from pyrogram.handlers import MessageHandler
from pyrogram.filters import command
from base64 import b64encode
from re import match as re_match, split as re_split
from asyncio import sleep
from aiofiles.os import path as aiopath

from bot import bot, LOGGER, config_dict
from bot.helper.ML.other.utils import is_url, is_magnet, is_mega_link, is_gdrive_link, get_content_type, new_task, sync_to_async, is_telegram_link
from bot.helper.ML.other.exceptions import DirectDownloadLinkException
from bot.helper.ML.aria2.aria2_engine import add_aria2c_download, start_aria2_listener
from bot.helper.ML.other.direct_link_generator import direct_link_generator
from bot.helper.ML.telegram.tg_download import TelegramDownloader
from bot.helper.other.commands import Commands
from bot.helper.ML.telegram.filters import CustomFilters
from bot.helper.ML.message.message_utils import sendMessage, get_tg_link_content
from bot.helper.ML.task.process_listener import ProcessListener
from bot.helper.ML.message.text import ML_HELP

start_aria2_listener()



DOWNLOAD_DIR = config_dict['DOWNLOAD_DIR']


@new_task
async def _m_l(client, message, isZip=False, extract=False, isLeech=False, sameDir={}):
    mesg = message.text.split('\n')
    message_args = mesg[0].split(maxsplit=1)
    ratio = None
    seed_time = None
    seed = False
    multi = 0
    link = ''
    folder_name = ''
    reply_to = None
    file_ = None
    session = ''

    if len(message_args) > 1:
        index = 1
        args = mesg[0].split(maxsplit=4)
        args.pop(0)
        for x in args:
            x = x.strip()
            if x == 'd':
                seed = True
                index += 1
            elif x.startswith('d:'):
                seed = True
                index += 1
                dargs = x.split(':')
                ratio = dargs[1] or None
                if len(dargs) == 3:
                    seed_time = dargs[2] or None
            elif x.isdigit():
                multi = int(x)
                mi = index
            elif x.startswith('m:'):
                marg = x.split('m:', 1)
                if len(marg) > 1:
                    folder_name = f"/{marg[1]}"
                    if not sameDir:
                        sameDir = set()
                    sameDir.add(message.id)
            else:
                break
        if multi == 0:
            message_args = mesg[0].split(maxsplit=index)
            if len(message_args) > index:
                x = message_args[index].strip()
                if not x.startswith(('n:', 'pswd:', 'up:', 'rcf:')):
                    link = re_split(r' pswd: | n: | up: | rcf: ', x)[0].strip()

        if len(folder_name) > 0:
            seed = False
            ratio = None
            seed_time = None

    @new_task
    async def __run_multi():
        if multi <= 1:
            return
        await sleep(4)
        nextmsg = await client.get_messages(chat_id=message.chat.id, message_ids=message.reply_to_message_id + 1)
        msg = message.text.split(maxsplit=mi+1)
        msg[mi] = f"{multi - 1}"
        nextmsg = await sendMessage(nextmsg, " ".join(msg))
        nextmsg = await client.get_messages(chat_id=message.chat.id, message_ids=nextmsg.id)
        if len(folder_name) > 0:
            sameDir.add(nextmsg.id)
        nextmsg.from_user = message.from_user
        await sleep(4)
        _m_l(client, nextmsg, isZip, extract, isLeech, sameDir)

    __run_multi()

    path = f'{DOWNLOAD_DIR}{message.id}{folder_name}'

    name = mesg[0].split(' n: ', 1)
    name = re_split(' pswd: | rcf: | up: ', name[1])[
        0].strip() if len(name) > 1 else ''

    pswd = mesg[0].split(' pswd: ', 1)
    pswd = re_split(' n: | rcf: | up: ', pswd[1])[0] if len(pswd) > 1 else None

    rcf = mesg[0].split(' rcf: ', 1)
    rcf = re_split(' n: | pswd: | up: ', rcf[1])[
        0].strip() if len(rcf) > 1 else None

    up = mesg[0].split(' up: ', 1)
    up = re_split(' n: | pswd: | rcf: ', up[1])[
        0].strip() if len(up) > 1 else None

    if len(mesg) > 1 and mesg[1].startswith('Tag: '):
        tag, id_ = mesg[1].split('Tag: ')[1].split()
        message.from_user = await client.get_users(id_)
        try:
            await message.unpin()
        except:
            pass
    elif username := message.from_user.username:
        tag = f"@{username}"
    else:
        tag = message.from_user.mention

    if link and is_telegram_link(link):
        try:
            reply_to, session = await get_tg_link_content(link)
        except Exception as e:
            await sendMessage(message, f'ERROR: {e}')
            return
    elif message.reply_to_message:
        reply_to = message.reply_to_message
        if reply_to.text is not None:
            reply_text = reply_to.text.split('\n', 1)[0].strip()
            if reply_text and is_telegram_link(reply_text):
                try:
                    reply_to, session = await get_tg_link_content(reply_text)
                except Exception as e:
                    await sendMessage(message, f'ERROR: {e}')
                    return

    if reply_to:
        file_ = reply_to.document or reply_to.photo or reply_to.video or reply_to.audio or \
            reply_to.voice or reply_to.video_note or reply_to.sticker or reply_to.animation or None
        if (re_user := reply_to.from_user) and not re_user.is_bot:
            if username := reply_to.from_user.username:
                tag = f"@{username}"
            else:
                tag = reply_to.from_user.mention

        if len(link) == 0 or not is_url(link) and not is_magnet(link):
            if file_ is None:
                reply_text = reply_to.text.split('\n', 1)[0].strip()
                if is_url(reply_text) or is_magnet(reply_text):
                    link = reply_text
            elif reply_to.document and (file_.mime_type == 'application/x-bittorrent' or file_.file_name.endswith('.torrent')):
                link = await reply_to.download()
                file_ = None

    if not is_url(link) and not is_magnet(link) and not await aiopath.exists(link) and file_ is None:
        await sendMessage(message, ML_HELP)
        return

    if link:
        LOGGER.info(link)

    if not is_mega_link(link) and not is_magnet(link) and not is_gdrive_link(link) and not link.endswith('.torrent') and file_ is None:
        content_type = await sync_to_async(get_content_type, link)
        if content_type is None or re_match(r'text/html|text/plain', content_type):
            try:
                link = await sync_to_async(direct_link_generator, link)
                LOGGER.info(f"Generated link: {link}")
            except DirectDownloadLinkException as e:
                LOGGER.info(str(e))
                if str(e).startswith('ERROR:'):
                    await sendMessage(message, str(e))
                    return

    if not isLeech:
        if up is None or up == 'rc':
            up = config_dict['RCLONE_PATH']
        if not up:
            await sendMessage(message, 'No Rclone Destination!')
            return
        if up.startswith('mrcc:'):
            config_path = f'rclone/{message.from_user.id}.conf'
        else:
            config_path = 'rclone.conf'
        if not await aiopath.exists(config_path):
            await sendMessage(message, f"Rclone Config: {config_path} not Exists!")
            return

    listener = ProcessListener(
        message, isZip, extract, isLeech, pswd, tag, seed, sameDir, rcf, up)

    if file_ is not None:
        await TelegramDownloader(listener).add_download(reply_to, f'{path}/', name, session)
    else:
        if len(mesg) > 1 and not mesg[1].startswith('Tag:'):
            ussr = mesg[1]
            pssw = mesg[2] if len(mesg) > 2 else ''
            auth = f"{ussr}:{pssw}"
            auth = "Basic " + b64encode(auth.encode()).decode('ascii')
        else:
            auth = ''
        await add_aria2c_download(link, path, listener, name, auth, ratio, seed_time)


async def mr(client, message):
    _m_l(client, message)


async def unzip_mr(client, message):
    _m_l(client, message, extract=True)


async def zip_mr(client, message):
    _m_l(client, message, True)


async def leech(client, message):
    _m_l(client, message, isLeech=True)


async def unzip_lc(client, message):
    _m_l(client, message, extract=True, isLeech=True)


async def zip_lc(client, message):
    _m_l(client, message, True, isLeech=True)



bot.add_handler(MessageHandler(leech, filters=command(
    Commands.LC) & CustomFilters.authorized))
bot.add_handler(MessageHandler(unzip_lc, filters=command(
    Commands.UnzipLC) & CustomFilters.authorized))
bot.add_handler(MessageHandler(zip_lc, filters=command(
    Commands.ZipLC) & CustomFilters.authorized))


bot.add_handler(MessageHandler(mr, filters=command(
    Commands.MC) & CustomFilters.authorized))
bot.add_handler(MessageHandler(unzip_mr, filters=command(
    Commands.UnzipMC) & CustomFilters.authorized))
bot.add_handler(MessageHandler(zip_mr, filters=command(
    Commands.ZipMC) & CustomFilters.authorized))