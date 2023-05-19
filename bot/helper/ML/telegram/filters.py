#!/usr/bin/env python3
from pyrogram.filters import create

from bot import user_data, config_dict

OWNER_ID = config_dict['OWNER_ID']


class CustomFilters:

    async def owner_filter(self, client, update):
        user = update.from_user or update.sender_chat
        uid = user.id
        return uid == OWNER_ID

    owner = create(owner_filter)

    async def authorized_user(self, client, update):
        user = update.from_user or update.sender_chat
        uid = user.id
        chat_id = update.chat.id
        return bool(uid == OWNER_ID or (uid in user_data and (user_data[uid].get('is_auth', False) or
                                                              user_data[uid].get('is_sudo', False))) or (chat_id in user_data and user_data[chat_id].get('is_auth', False)))

    authorized = create(authorized_user)

    async def sudo_user(self, client, update):
        user = update.from_user or update.sender_chat
        uid = user.id
        return bool(uid == OWNER_ID or uid in user_data and user_data[uid].get('is_sudo'))

    sudo = create(sudo_user)
