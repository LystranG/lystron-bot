from nonebot.adapters.onebot.v11 import Bot as V11Bot
import asyncio, time

def _is_expired(timestamp: int):
    now = int(time.time())
    return now - timestamp >= 100

async def _recall(bot: V11Bot, delete_list: list):
    for msg_id in delete_list:
        await bot.delete_msg(message_id=msg_id)
        await asyncio.sleep(0.5)


async def recall_friend(
        bot: V11Bot,
        user_id: int,
        count: int
):
    async def request(c: int):
        return await bot.call_api(
            "get_friend_msg_history",
            user_id=user_id,
            message_seq=0,
            count=c,
            reverse_order=False
        )
    
    await _compute(bot, count, request)


async def recall_group(
        bot: V11Bot,
        group_id: int,
        count: int
):
    async def request(c: int):
        return await bot.call_api(
            "get_group_msg_history",
            group_id=group_id,
            message_seq=0,
            count=c,
            reverse_order=False
        )
    await _compute(bot, count, request)
    

async def _compute(bot: V11Bot, count: int, request):
    try:
        delete_list = []
        cnt = count
        loop_cnt = 0
        while cnt > 0 and loop_cnt <= 5:
            amount = (loop_cnt + 1) * count
            res = await request(amount)
            messages = res["messages"]
            
            if not messages or len(messages) == 0:
                break
            expire_flag = False
            for i in reversed(range(0, count)):
                msg = messages[i]
                if msg["self_id"] != msg["user_id"] or msg["raw_message"] == '':
                    continue
                if _is_expired(int(msg["time"])):
                    expire_flag = True
                    break
                delete_list.append(msg["message_id"])
                cnt -= 1
                if cnt <= 0:
                    break
            if len(messages) < amount or expire_flag:
                break
            loop_cnt += 1
            
        await _recall(bot, delete_list)
    except Exception:
        return
