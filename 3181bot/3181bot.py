import discord as d
from discord.ext import commands as com

import json
import pickle
import functools
from os import path
import random

from fuzzywuzzy import process

class dotdict(dict):
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

class RegistrationData:

    def __init__(self, student_sects):
        self.registered_ids = {}
        self.group_num = {}
        self.registered_names = set()
        self.student_sects = student_sects
        self.name_opts = {}
        self.need_confirm = set()
        self.last_added = None

with open('../config.json', 'r') as f:
    config = json.loads(f.read(), object_pairs_hook=dotdict)
    config.section_idx = dict(zip(config.sections,range(len(config.sections))))

DATNAME = "registration.data"
rd = None

def read_dat():
    global rd
    with open('student_sections.csv', 'r') as f:
        lines = iter(f)
        next(lines) # ignore csv headers
        student_sects = dict(map(lambda s: s.strip().split(','), lines))
    rd = RegistrationData(student_sects)

def write_dat():
    with open(DATNAME, 'wb') as f:
        pickle.dump(rd,f)

if path.exists(DATNAME):
    try:
        with open(DATNAME, 'rb') as f:
            rd = pickle.load(f)
    except:
       read_dat()
       write_dat()
else:
    read_dat()
    write_dat()

bot = com.Bot(command_prefix='!')
guild = None

student_text_overwrites = None
student_voice_overwrites = None

@bot.event
async def on_ready():
    global guild, default_text_overwrites, student_text_overwrites, default_voice_overwrites, student_voice_overwrites
    guild = d.utils.get(bot.guilds, name=config.server_name)
    print('{} has connected to {}(id: {})'.format(bot.user, guild.name, guild.id))

    student_text_overwrites = d.PermissionOverwrite(view_channel=True)
    student_voice_overwrites = d.PermissionOverwrite(view_channel=True, stream=True)

    channels = await guild.fetch_channels()
    new_member = d.utils.get(channels, name="new-member")
    async for mess in new_member.history(limit=1):
        break
    else:
        await new_member.send('\n'.join((
            'Welcome to the ITSC 3181 Discord Server!',
            '',
            'In order to be able to see the actual contents of this server, you first need to regiser',
            'To do so, right click on my name or avatar (on mobile, press on my avatar or long press on my name), and click on `Message`. It will bring you to a direct message with me. Then send me the message `!register`, and follow the directions I give',
            '',
            'If you are having any issues, contact a TA. You should see an icon that looks like two people in the top right corner. Click on that, and you should see at least one TA (it may already be clicked if you are on a laptop or destop)',
            '',
            'If your name does not appear during the regstration process **do not** register under someone else\'s name. Contact a TA instead, and they can manually add you to my database'
        )))

@bot.command()
async def addstudent(ctx, *args):
    await _addstudent(ctx, *args)
    write_dat()

async def _addstudent(ctx, *args):
    user = ctx.author
    dm = user.dm_channel
    if dm is None:
        await user.create_dm()
        dm = user.dm_channel

    mem = await guild.fetch_member(user.id)
    TA = d.utils.get(mem.roles, name='TA')
    if TA is None:
        await dm.send('You do not have permission to use this command.')
        return

    if len(args) == 0:
        await dm.send('\n'.join((
            'Command usage: `!addstudent <section> <name>`',
            'Example:',
            '```',
            '!addstudent 001 John Smith',
            '```',
            'The section is the first argument, and all successive arguments are assumed to be the name of the student. The valid sections are:'
            '```',
            str(config.sections),
            '```'
            'Once you pass in the necessary arguments, the student will be semi-permanently added. You can use `!removelast` to remove the last student added, but all students added before will be permanently added. Only deleting `registration.data` will remove them, which is not recommended, as it also removes all group and registration data.'
        )))
        return

    sect, *fullname = args
    if sect not in config.sections:
        await dm.send('That is not a valid section. Enter `!addstudent` with no parameters to see the valid section names')
        return
    fullname = ' '.join(name.capitalize() for name in fullname)
    rd.last_added = fullname
    rd.student_sects[fullname] = sect
    await dm.send('Added "{}" in section "{}"'.format(fullname,sect))

@bot.command()
async def removelast(ctx):
    await _removelast(ctx)
    write_dat()

async def _removelast(ctx):
    user = ctx.author
    dm = user.dm_channel
    if dm is None:
        await user.create_dm()
        dm = user.dm_channel()

    mem = await guild.fetch_member(user.id)
    TA = d.utils.get(mem.roles, name='TA')
    if TA is None:
        await dm.send('You do not have permission to use this command.')
        return

    fullname = rd.last_added
    if fullname == None:
        await dm.send('No student recently added to remove')
        return
    if fullname in rd.registered_names:
        await dm.send('A student already registered with that name')
        return
    rd.last_added = None
    del rd.student_sects[fullname]
    await dm.send('Removed "{}"'.format(fullname))

@bot.command()
async def repo(ctx):
    user = ctx.author
    dm = user.dm_channel
    if dm is None:
        await user.create_dm()
        dm = user.dm_channel
    
    await dm.send('I see you like to snoop around. Here\'s my code:\nhttps://github.com/JCRaymond/3181Discord\n\n(it\'s public on github anyways)')

@bot.command()
async def resetregistration(ctx, *args):
    await _resetregistration(ctx, *args)
    write_dat()

async def _resetregistration(ctx, *args):
    user = ctx.author
    dm = user.dm_channel
    if dm is None:
        await user.create_dm()
        dm = user.dm_channel
    
    mem = await guild.fetch_member(user.id)
    
    if mem.id not in rd.registered_ids:
        await dm.send('\n'.join((
            'You must already be registered in order to reset the registration!',
            'You may simply enter `!register` to start over the registration process if you are still in the process'
        )))
        return

    reg_name = rd.registered_ids[mem.id]
    del rd.registered_ids[mem.id]
    rd.registered_names.remove(reg_name)
    await mem.edit(nick=None, roles=[])
    await dm.send(
        'Registration reset! You can use `!register` to register now'
    )

async def get_smallest_group_num(sect):
    num_groups = config.num_groups[config.section_idx[sect]]
    tc_name_temp = 'lab-{}-group-{{}}'.format(sect)
    min_size = float('inf')
    min_group_nums = []
    channels = await guild.fetch_channels()
    for group_num in range(1,num_groups+1):
        tc_name = tc_name_temp.format(group_num)
        channel = d.utils.get(channels, name=tc_name)
        num_members = len(channel.overwrites)-2
        if num_members < min_size:
            min_size = num_members
            min_group_nums = [group_num]
        elif num_members == min_size:
            min_group_nums.append(group_num)
    return random.choice(min_group_nums)
 
@bot.command()
async def register(ctx, *args):
    await _register(ctx, *args)
    write_dat()

async def _register(ctx, *args):
    user = ctx.author
    dm = user.dm_channel
    if dm is None:
        await user.create_dm()
        dm = user.dm_channel
    
    mem = guild.get_member(user.id)

    if mem.id in rd.registered_ids:
        await dm.send(
            'You have already registered! If you absolutely wish to restart the registration process, enter `!resetregistration`'
        )
        return

    if not args:
        await dm.send('\n'.join((
            'Hello {}!'.format(mem.name),
            ''
            'Please enter the command `!register <Full Name>`. Example:',
            '```',
            '!register John Smith',
            '```',
            'For your name, please enter your name as it appears on Canvas',
            'If you have a different prefered name from how it appears on Canvas, contact a TA once you have finished registering',
            '',
            'At any point, if you mess up the registration process, just re-input `!register` to start over'
        )))
        return

    farg = args[0]
    if (len(farg) < 1 or farg[0] != '#') and mem.id not in rd.need_confirm:
        name = ' '.join(args)
        fname = farg
        student_names = list(rd.student_sects)
        options = process.extract(name, student_names, limit=3)
        opt_names = [opt[0] for opt in options]

        msg_start = [
            'Hello {}, I found these people in the course:'.format(fname),
            '```'
        ]
        msg_end = [
            '```',
            'If one of these people listed is you, enter the command `!register #<Number>`. Example:',
            '```',
            '!register #2',
            '```',
            'Otherwise, retry entering your name with the register command, or contact a TA'
        ]

        msg_middle = []
        for i, (sname, prob) in enumerate(options):
            sect = rd.student_sects[sname]
            idx = config.section_idx[sect]
            time = config.times[idx]
            msg_middle.append("{}) '{}' in section {} at {} - {}% match".format(i+1,sname,sect,time,prob))

        await dm.send('\n'.join(msg_start + msg_middle + msg_end))
        rd.name_opts[mem.id] = opt_names
        return

    if mem.id not in rd.name_opts:
        await dm.send(
            'Please enter the command `!register` and follow the directions'
        )
        return
    
    if mem.id not in rd.need_confirm:
        opts = rd.name_opts[mem.id]
        choice = int(farg[1])-1
        if choice < 0 or choice > 2:
            await dm.send(
                'Your selection must be an integer between 1 and 3'
            )
            return
        chosen_name = opts[choice]
        if chosen_name in rd.registered_names:
            await dm.send(
                'Someone has already registered that name! If you believe this is an error, contact a TA'
            )
            return
        sect = rd.student_sects[chosen_name]
        time = config.times[config.section_idx[sect]]
        rd.name_opts[mem.id] = (chosen_name, sect, time)
        rd.need_confirm.add(mem.id)
        await dm.send(
            "You have selected '{}' in section {} at {}.\n".format(chosen_name,sect,time)+
            'If you are certain about your choice, please enter `!register yes`\n'+
            'Otherwise, enter `!register no`, and start over\n'
        )
        return

    rd.need_confirm.remove(mem.id)
    resp = farg
    if resp.lower() != 'yes':
        await dm.send(
            'You have chosen to cancel your choice. Enter `!register` to start over'
        )
        del rd.name_opts[mem.id]
        return

    chosen_name, sect, time = rd.name_opts[mem.id]
    del rd.name_opts[mem.id]
    student_role = d.utils.get(guild.roles, name='Student')
    section_role = d.utils.get(guild.roles, name=sect)
    rd.registered_names.add(chosen_name)
    rd.registered_ids[mem.id] = chosen_name
    await mem.edit(nick=chosen_name, roles=[student_role, section_role])
    
    if mem.id in rd.group_num:
        group = rd.group_num[mem.id]
    else:
        group = await get_smallest_group_num(sect)
        rd.group_num[mem.id] = group
    group_tc_name = 'lab-{}-group-{}'.format(sect,group)
    text_channel = d.utils.get(guild.channels, name=group_tc_name)
    text_overwrites = text_channel.overwrites
    text_overwrites[mem] = student_text_overwrites
    await text_channel.edit(overwrites=text_overwrites)

    group_vc_name = 'Lab {} - Group {}'.format(sect,group)
    voice_channel = d.utils.get(guild.channels, name=group_vc_name)
    voice_overwrites = voice_channel.overwrites
    voice_overwrites[mem] = student_voice_overwrites
    await voice_channel.edit(overwrites=voice_overwrites)

    print("Registered '{}' as '{}'".format(mem.name,chosen_name))

    chosen_fname = chosen_name.split()[0]
    await dm.send(
        'Congrats {}, you have been registered as {}, and placed in group number {}! You should now have the correct permissions and nickname on the server.\nIf you registered under the wrong name, please enter the command `!resetregistration`.\nIf your nickname is not correct, or you do not have the right permissions, but you did register the correct name, please contact a TA.'.format(mem.name,chosen_fname,group)
    )

bot.run(config.token)

