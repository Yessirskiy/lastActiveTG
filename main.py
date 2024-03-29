import tomllib
from loguru import logger
from typing import Literal

from telethon import TelegramClient
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import (
    UserStatusOffline,
    UserStatusOnline,
    UserStatusRecently,
    UserStatusLastWeek,
    UserStatusLastMonth
)

import random
import time
import os
import sys
import asyncio
import threading
import math

statuses_to_files = {
    "Error" : "errors.txt",
    "Bot" : "bots.txt",
    "Last seen recently" : "recently.txt",
    "Last seen week ago" : "week.txt",
    "Last seen month ago" : "month.txt",
    "Last seen long time ago" : "longtime.txt"
}

def get_or_create_eventloop():
    try:
        return asyncio.get_event_loop()
    except RuntimeError as ex:
        if "There is no current event loop in thread" in str(ex):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return asyncio.get_event_loop()

def setLogging(): 
    try:
        if not os.path.exists(config['Logging']['logs_folder']):
            os.mkdir(config['Logging']['logs_folder'])

        logger.remove()
        logger.add(sys.stderr, level=config["Logging"]["console_level"])

        sink = os.path.join(config['Logging']['logs_folder'], config['Logging']['sink'])
        logger.add(sink=sink, level=config['Logging']["write_level"], format=config['Logging']['format'], rotation=config['Logging']['rotation'], compression=config['Logging']['compression'])
    except PermissionError:
        print("Coulnd't create logs folder, run in administrator mode")
    except KeyError:
        print("Settings are not completed. Check config file")

def getConfig(filename: str = "config.toml") -> dict | Literal[False]:
    try:
        with open(filename, "rb") as file:
            data = tomllib.load(file)
        return data
    except FileNotFoundError:
        print(f"Config file named {filename} is not found.")
    return False

def parseStatus(status):
    if isinstance(status, UserStatusOffline):
        #date = datetime.datetime.now(datetime.timezone.utc) - status.was_online
        return f"Last seen on {status.was_online.strftime('%d/%m/%Y, %H:%M')}"
    if isinstance(status, UserStatusOnline):
        return "Currently online"
    elif isinstance(status, UserStatusRecently):
        return "Last seen recently"
    elif isinstance(status, UserStatusLastWeek):
        return "Last seen week ago"
    elif isinstance(status, UserStatusLastMonth):
        return "Last seen month ago"
    else:
        return "Last seen long time ago"
        
def toFile(username: str, status: str):
    filename = os.path.join(config["General"]["results_folder"], statuses_to_files.get(status, f"{status.split(',')[0].split('/', 1)[1].replace('/', '-')}.txt"))
    if not os.path.exists(filename):
        open(filename, 'w').close()

    # if status not in statuses_to_files.keys():
    #     line = "@" + username + " | " + status
    # else:
    #     line = "@" + username
    line = "@" + username
    
    with open(filename, 'a', encoding="utf-8") as file:
        logger.debug(f"Writing {line} to {filename}")
        file.write(line + '\n')

def eraseFromMain(username: str):
    with open(config["General"]["users_list"], 'r', encoding="utf-8") as file:
        raw = file.read().splitlines()
        usernames = list([line.strip() for line in raw if line.strip() != ""])
    logger.debug(f"Remove @{username} from main list")
    usernames.remove(username)
    with open(config["General"]["users_list"], 'w', encoding="utf-8") as file:
        file.write('\n'.join(usernames))

async def getStatuses(client: TelegramClient, usernames: list, delay: list):
    logger.info(f"Start retrieving information of users in a list...")
    logger.debug(f"Total length of usernames: {len(usernames)}. Delay range: {delay}")
    statuses = {}
    await client.sign_in()
    for username in usernames:
        try:
            logger.debug(f"Getting full information of {username}")
            full = await client(GetFullUserRequest(username))
            if not full.users[0].bot:
                status = parseStatus(full.users[0].status)
                statuses[username] = status
            else:
                status = "Bot"
                statuses[username] = "Bot"
        except Exception as e:
            if isinstance(e, TypeError):
                logger.error(f"Username doesn't belong to User. Args: {e.args}")
                status = "Error"
                statuses[username] = "Error"
            else:
                logger.error(f"Error while getting info of {username}: {e}")
                status = "Error"
                statuses[username] = "Error"
        finally:
            toFile(username, status)
            eraseFromMain(username)

        logger.info(f"@{username} | {status}")
        sleep = random.randint(delay[0], delay[1])
        logger.debug(f"Sleeping for {sleep} seconds")
        time.sleep(sleep)

    return statuses

#def distributeToFiles(statuses: dict):
    nv_statuses = {}
    logger.debug(f"Reversing an intial statuses dict")
    for k, v in statuses.items():
        status = statuses_to_files.get(v, "exacttime.txt")
        if status not in nv_statuses.keys():
            nv_statuses[status] = []

        if status == "exacttime.txt":
            nv_statuses[status].append(k + " | " + statuses[k])
        else:
            nv_statuses[status].append(k)

    

    if config["General"]["clear_results"]:
        files = os.listdir(config["General"]["results_folder"])
        for file in files:
            logger.debug(f"Deleting {file}...")
            os.remove(os.path.join(config['General']['results_folder'], file))
            
    for k, v in nv_statuses.items():
        file = os.path.join(config["General"]["results_folder"], k)
        logger.debug(f"Writing usernames to {k}")
        with open(file, "r", encoding="utf-8") as f:
            accs = f.read().splitlines()
        done = accs + v
        with open(file, 'w', encoding="utf-8") as f:                    
            f.write("\n".join(done))

def run(client: TelegramClient, usernames: list, delay: list):
    loop = get_or_create_eventloop()
    future = asyncio.ensure_future(getStatuses(client, usernames, delay))
    loop.run_until_complete(future)

def main():
    try:
        if not os.path.exists(config["General"]["sessions_folder"]): 
            logger.debug(f"Creating folder for sessions: {config['General']['sessions_folder']}")
            os.mkdir(config["General"]["sessions_folder"])

        if not os.path.exists(config["General"]["results_folder"]):
            logger.debug(f"Creating folder for results: {config['General']['results_folder']}")
            os.mkdir(config["General"]["results_folder"])
        
        
        sessions = os.listdir(config["General"]["sessions_folder"])
        if len(sessions) == 0:
            logger.error(f"Please, insert session files into sessions folder...")
            return
        clients = [TelegramClient(session=os.path.join(config["General"]["sessions_folder"], client)) for client in sessions]
            

        delay_raw = config["General"]["delay"]
        logger.debug(f"Parsing delay: {delay_raw}")
        if "-" in delay_raw:
            delay_range = [int(delay) for delay in delay_raw.split("-")]   
        else:
            logger.error(f"Please, make sure delay range provided correctly in configuration file (e.g. 5-10)")
            return

        with open(config["General"]["users_list"], 'r', encoding="utf-8") as file:
            logger.debug(f"Parsing usernames from {config['General']['users_list']}")
            raw = file.read().splitlines()
            usernames = [line.strip() for line in raw if line.strip() != ""]
        
        amount = math.ceil(len(usernames) / len(clients))
        counter = 0
        logger.debug(f"Usernames to check from one acc: {amount}")
        for client in clients:
            logger.debug(f"Launching {client}... To check: {counter} - {counter + amount}")
            threading.Thread(target=run, args=(client, usernames[counter:(counter+amount)], sorted(delay_range),)).start()
            counter += amount

        while True:
            rest = open(config["General"]["users_list"], 'r', encoding="utf-8").read().splitlines()
            if len(rest) == 0:
                break
            time.sleep(5)
        logger.success(f"Finished checking all the usernames")
    except ValueError:
        logger.error(f"Please, check if all the credentials provided in configuration file are valid and non-empty.")
        return
    except FileNotFoundError:
        logger.error(f"Please, make sure that file with username exists and spelled correctly in configuration file.")
        return

if __name__ == "__main__":
    config = getConfig()
    setLogging()
    client = TelegramClient("main", config["Telegram"]["api_id"], config["Telegram"]["api_hash"]) 
    main()
    input("Press ENTER to exit...")