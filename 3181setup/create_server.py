import discord as d
import json
from collections import OrderedDict

class dotdict(dict):
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

with open('../config.json', 'r') as f:
    config = json.loads(f.read(), object_pairs_hook=dotdict)

client = d.Client()

global guild
guild = None

global inv_channel
inv_channel = None

async def cancel():
    await client.logout()
    await client.close()

async def clear_guild_channels(guild):
    channels = await guild.fetch_channels()
    for channel in channels:
        await channel.delete()

with open('default_aliases.json','r') as f:
    default_aliases = json.loads(f.read())

def dealias_list(lst, aliases):
    for e in lst:
        if e in aliases:
            yield from dealias_list(aliases[e], aliases)
        else:
            yield e

def process_template(val):
    if isinstance(val, int):
        yield from map(str,range(1, val+1))
    elif isinstance(val, list):
        yield from map(str,val)
    else:
        yield val

def process_color(color, aliases):
    if color in aliases:
        color = aliases[color]
    return d.Color(int(color,16))

def process_permissions(permissions, aliases, cls=d.Permissions):
    if not isinstance(permissions, list):
        permissions = [permissions]
    perm_vals = {}
    for permission in dealias_list(permissions, aliases):
        if permission.startswith('~'):
            perm_vals[permission[1:]] = False
        else:
            perm_vals[permission] = True
    return cls(**perm_vals)

roles = None
def process_overwrites(guild, overwrites, aliases, templates=None):
    ret = {}
    if templates is not None:
        for name, perms in overwrites.items():
            role = guild.default_role
            if name != 'default':
                if name.startswith('##'):
                    name = name[2:]
                    for template in templates:
                        name = name.replace(*template)
                role = d.utils.get(roles, name=name)
            perms = process_permissions(perms, aliases, cls=d.PermissionOverwrite)
            ret[role]=perms
    else:
        for name, perms in overwrites.items():
            role = guild.default_role
            if name != 'default':
                role = d.utils.get(roles, name=name)
            perms = process_permissions(perms, aliases, cls=d.PermissionOverwrite)
            ret[role]=perms
    return ret

async def create_role(guild, name, settings, aliases):
    if settings is None:
        settings = {}
    else:
        settings = dict(settings)
    if 'permissions' not in settings:
        settings['permissions'] = []
    settings['permissions'] = process_permissions(settings['permissions'],aliases)
    if 'color' in settings:
        settings['color'] = process_color(settings['color'], aliases)
    isbotrole = False
    if 'botrole' in settings:
        isbotrole = True
        del settings['botrole']
    role = None
    if name == 'default':
        role = await guild.default_role.edit(**settings)
    else:
        role = await guild.create_role(name=name, **settings)
    if isbotrole:
        return role
    return None

async def create_roles(guild, roles, aliases, template_vals):
    botrole = None
    for name, settings in roles.items():
        if name.startswith('##'):
            if 'template' not in settings:
                print(f'Must provide template name for templated role "{name}"')
                return False
            name = name[2:]    
            settings = dict(settings)
            template_name = settings['template']
            del settings['template']
            template_rep = f'<{template_name}>'
            for tempval in process_template(template_vals[template_name]):
                subname = name.replace(template_rep, tempval)
                role = await create_role(guild, subname, settings, aliases)
                if role is not None:
                    botrole = role
        else:
            role = await create_role(guild, name, settings, aliases)
            if role is not None:
                botrole = role
    
    if botrole is None:
        print('At least one role must have "botrole" property set as true')
        return False
    owner = await guild.fetch_member(guild.owner_id)
    await owner.edit(roles = [botrole])
    return True

def sync_overwrites(parent_overwrites, child_overwrites):
    new_overwrites = dict(parent_overwrites)
    for role, child_ow in child_overwrites.items():
        if role not in new_overwrites:
            new_overwrites[role] = child_ow
            continue
        new_ow = new_overwrites[role]
        new_ow.update(**child_ow._values)
    return new_overwrites

async def create_channel(guild, ctype, name, settings, aliases, template_vals, category=None, templates=None):
    if settings is None:
        settings = {}
    else:
        settings = dict(settings)
    if name.startswith('##'):
        if 'template' not in settings:
            if templates is None:
                print(f'Must provide template name for the templated channel "{name}"')
                return False
            name = name[2:]
            for template in templates:
                name = name.replace(*template)
            success = await create_channel(guild, ctype, name, settings, aliases, template_vals, category, templates)
            if not success:
                return False
            return True
        name = name[2:]
        template_name = settings['template']
        del settings['template']
        if template_name.startswith('##'):
            template_name = template_name[2:]
            for template in templates:
                template_name = template_name.replace(*template)
        template_rep = f'<{template_name}>'
        if templates is None:
            templates = []
        for tempval in process_template(template_vals[template_name]):
            new_templates = templates + [(template_rep, tempval)]
            subname = name
            for template in new_templates:
                subname = subname.replace(*template)
            success = await create_channel(guild, ctype, subname, settings, aliases, template_vals, category, new_templates)
            if not success:
                return False
        return True
    overwrites = process_overwrites(guild, settings, aliases, templates)
    if category is not None:
        overwrites = sync_overwrites(category.overwrites, overwrites) 
    op = guild.create_text_channel
    if ctype == 'voice':
        op =  guild.create_voice_channel
    await op(name, overwrites=overwrites, category=category)
    return True


async def create_category(guild, name, settings, aliases, template_vals, templates=None):
    if settings is None:
        settings = {}
    else:
        settings = dict(settings)
    if name.startswith('##'):
        if 'template' not in settings:
            print(f'Must provide template name for the templated category "{name}"')
        name = name[2:]
        template_name = settings['template']
        del settings['template']
        template_rep = f'<{template_name}>'
        for tempval in process_template(template_vals[template_name]):
            subname = name.replace(template_rep, tempval)
            success = await create_category(guild, subname, settings, aliases, template_vals, [(template_rep, tempval),])
            if not success:
                return False
        return True
    channels = settings.get('channels',{})
    overwrites = settings.get('overwrites', {})
    overwrites = process_overwrites(guild, overwrites, aliases, templates)
    category = await guild.create_category(name, overwrites=overwrites)
    category = await client.fetch_channel(category.id)
    for channel, channel_settings in channels.items():
        ctype, _, name = channel.partition(':')
        success = await create_channel(guild, ctype, name, channel_settings, aliases, template_vals, category, templates)
        if not success:
            return False
    return True

async def create_channels(guild, channels, aliases, templates):
    global roles
    roles = await guild.fetch_roles()
    for name, settings in channels.items():
        if settings is None:
            settings = {}
        ctype, _, name = name.partition(':')
        if ctype == 'category':
            success = await create_category(guild, name, settings, aliases, templates)
            if not success:
                return False
        elif ctype == 'text' or ctype == 'voice':
            success = await create_channel(guild, ctype, name, settings, aliases, templates)
            if not success:
                return False
    return True

async def apply_layout(guild, layout):
    await clear_guild_channels(guild)
    templates = layout.get('templates', {})
    aliases = layout.get('aliases', {})
    aliases.update(default_aliases)
    roles = layout.get('roles', {})
    channels = layout.get('channels',{})
    success = await create_roles(guild, roles, aliases, templates)
    if not success:
        return False
    return await create_channels(guild, channels, aliases, templates)

@client.event
async def on_ready():
    global guild, inv_channel
    guild_name = config.server_name
    guild = d.utils.get(client.guilds, name=config.server_name)
    if guild is not None:
        if guild.owner != guild.me:
            print('Already set up server with that name, cancelling.')
            await cancel()
            return
        print('Still owner of server with that name, deleting...')
        await guild.delete()
    
    print('Creating guild with following properties...')
    print(f'\tName: {config.server_name}')
    print(f'\tSections: {config.sections}')
    print(f'\tNum Groups: {config.num_groups}')
    print()
    
    resp = input('Create server? (y/N): ')
    if resp == '' or resp[0].lower() != 'y':
        print('Cancelling.')
        await cancel()
        return
    
    print('Creating Server... ', end='')
    with open('xor.png', 'rb') as avatar:
        guild = await client.create_guild(guild_name, d.VoiceRegion.us_east, avatar.read())
    print('\t\tDone!')

    print('Reading layout... ', end='')
    with open('layout.json', 'r') as f:
        layout = json.loads(f.read(), object_pairs_hook=OrderedDict)

    templates = layout.get('templates',OrderedDict())
    templates['section'] = config.sections
    for section, num_groups in zip(config.sections,config.num_groups):
        templates[f'group_counter{section}'] = num_groups
    layout['templates'] = templates
    print('\t\tDone!')

    print('Applying layout...')
    success = await apply_layout(guild, layout)
    if not success:
        print('Application of layout unsuccessful, deleting guild...')
        await guild.delete()
        await cancel()
        return
    print('Server successfully setup!')
   
    channels = (await guild.fetch_channels())
    inv_channel = None
    for channel in channels:
        if isinstance(channel, d.TextChannel) or isinstance(channel, d.VoiceChannel):
            inv_channel = channel
            break
    inv = await inv_channel.create_invite(reason='Add owner to server', max_uses = 1)
    print('Open the following link to be given ownership to the server.')
    print('')
    print(f'\t{inv.url}')
    print('')

@client.event
async def on_member_join(member):
    if member.guild == guild:
        await guild.edit(owner = member)
        await cancel() 
        print(f'{member.name} given ownership!')
        print('Done.')

async def stuff():
    
    default_text_overwrites = {
        guild.default_role: d.PermissionOverwrite(view_channel=False),
        TA: d.PermissionOverwrite(view_channel=True)
    }
    student_text_overwrites = d.PermissionOverwrite(view_channel=True)

    default_voice_overwrites = {
        guild.default_role: d.PermissionOverwrite(view_channel=False, connect=False),
        TA: d.PermissionOverwrite(view_channel=True, connect=True)
    }
    student_voice_overwrites = d.PermissionOverwrite(view_channel=True, connect=True, stream=True)
    
    print(f'{client.user} has connected to {guild.name}(id: {guild.id})')
    with open('student_groups.csv', 'r') as f:
        lines = iter(f)
        next(lines) # ignore csv headers
        for line in lines:
            lab, group, *students = line.strip().split(',')
            
            text_channel_name = f'lab-0{lab}-group-{group}'
            voice_channel_name = f'Lab 0{lab} - Group {group}'

            text_channel = d.utils.get(guild.channels, name=text_channel_name)
            if text_channel is None:
                print('Text channel "{text_channel_name}" does not exist')
                break

            voice_channel = d.utils.get(guild.channels, name=voice_channel_name)
            if voice_channel is None:
                print('Voice channel "{voice_channel_name}" does not exist')
                break
            
            text_overwrites = dict(default_text_overwrites)
            voice_overwrites = dict(default_voice_overwrites)
            for student in students:
                mem = guild.get_member_named(student)
                if mem is None:
                    continue
                text_overwrites[mem] = student_text_overwrites
                voice_overwrites[mem] = student_voice_overwrites
            await text_channel.edit(overwrites=text_overwrites)
            print(f'Updated text channel "{text_channel}"')
            await voice_channel.edit(overwrites=voice_overwrites)
            print(f'Updated voice channel "{voice_channel}"')
            
    await client.logout()
    await client.close()

client.run(config.token)

