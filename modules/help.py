# Copyright (C) 2008-2011 Dejan Muhamedagic <dmuhamedagic@suse.de>
# Copyright (C) 2013 Kristoffer Gronlund <kgronlund@suse.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

'''
The commands exposed by this module all
get their data from the doc/crm.8.txt text
file. In that file, there are help for
 - topics
 - levels
 - commands in levels

The help file is lazily loaded when the first
request for help is made.

All help is in the following form in the manual:
[[cmdhelp_<level>_<cmd>,<short help text>]]
=== ...
Long help text.
...
[[cmdhelp_<level>_<cmd>,<short help text>]]

Help for the level itself is like this:

[[cmdhelp_<level>,<short help text>]]
'''

import os
import re
from utils import page_string
from msg import common_err
import config
import clidisplay
from ordereddict import odict


class HelpEntry(object):
    def __init__(self, short_help, long_help=''):
        self.short = short_help
        self.long = long_help

    def paginate(self):
        '''
        Display help, paginated.
        Replace asciidoc syntax with colorized output where possible.
        '''
        short_help = self.short
        long_help = self.long
        if long_help:
            display = clidisplay.CliDisplay.getInstance()
            short_help = display.attr_name(short_help)
            long_help = re.sub(r'`([^`]+)`', display.keyword(r'\1'), long_help)
        page_string(short_help + '\n' + long_help)

    def __str__(self):
        if self.long:
            return self.short + '\n' + self.long
        return self.short

    def __repr__(self):
        return str(self)


HELP_FILE = os.path.join(config.DATADIR, config.PACKAGE, "crm.8.txt")

_DEFAULT = HelpEntry('No help available')
_REFERENCE_RE = re.compile(r'<<[^,]+,(.+)>>')

# loaded on demand
# _LOADED is set to True when an attempt
# has been made (so it won't be tried again)
_LOADED = False
_TOPICS = odict()
_LEVELS = odict()
_COMMANDS = odict()


def help_overview():
    '''
    Returns an overview of all available
    topics and commands.
    '''
    _load_help()
    s = "Available topics:\n\n"
    for title, topic in _TOPICS.iteritems():
        s += "\t%-16s %s\n" % (title, topic.short)
    s += "\n"
    s += "Available commands:\n\n"
    for title, level in _LEVELS.iteritems():
        s += "\t%-16s %s\n" % (title, level.short)
        if title in _COMMANDS:
            for cmdname, cmd in _COMMANDS[title].iteritems():
                s += "\t\t%-16s %s\n" % (cmdname, cmd.short)
            s += "\n"
    return HelpEntry('Help overview for crmsh\n', s)


def help_topics():
    '''
    Returns an overview of all available
    topics.
    '''
    _load_help()
    s = ''
    for title, topic in _TOPICS.iteritems():
        s += "\t%-16s %s\n" % (title, topic.short)
    return HelpEntry('Available topics\n', s)


def help_topic(topic):
    '''
    Returns a help entry for a given topic.
    '''
    _load_help()
    return _TOPICS.get(topic, _DEFAULT)


def help_level(level):
    '''
    Returns a help entry for a given level.
    '''
    _load_help()
    return _LEVELS.get(level, _DEFAULT)


def help_command(level, command):
    '''
    Returns a help entry for a given command
    '''
    _load_help()
    if not level in _COMMANDS:
        return _DEFAULT
    return _COMMANDS[level].get(command, _DEFAULT)


def _is_help_topic(arg):
    return arg and arg[0].isupper()


def help_contextual(context, topic):
    """
    Displays and paginates
    """
    if (not topic and context == '.'):
        return help_overview()
    elif topic == 'topics':
        return help_topics()
    elif _is_help_topic(topic):
        return help_topic(topic)
    elif topic in _LEVELS:
        return help_level(topic)
    return help_command(context, topic)


def add_help(entry, topic=None, level=None, command=None):
    '''
    Takes a help entry as argument and inserts it into the
    help system.

    Used to define some help texts statically, for example
    for 'up' and 'help' itself.
    '''
    if topic:
        if topic not in _TOPICS or _TOPICS[topic] is _DEFAULT:
            _TOPICS[topic] = entry
    elif level and command:
        if level not in _COMMANDS:
            _COMMANDS[level] = odict()
        lvl = _COMMANDS[level]
        if command not in lvl or lvl[command] is _DEFAULT:
            lvl[command] = entry
    elif level:
        if level not in _LEVELS or _LEVELS[level] is _DEFAULT:
            _LEVELS[level] = entry


def _load_help():
    '''
    Lazily load and parse crm.8.txt.
    '''
    global _LOADED
    if _LOADED:
        return
    _LOADED = True

    def parse_header(line):
        'returns a new entry'
        entry = {'type': '', 'name': '', 'short': '', 'long': ''}
        line = line[2:-3]  # strip [[ and ]]\n
        info, short_help = line.split(',', 1)
        entry['short'] = short_help.strip()
        info = info.split('_')
        if info[0] == 'topics':
            entry['type'] = 'topic'
            entry['name'] = info[1]
        elif info[0] == 'cmdhelp':
            if len(info) == 2:
                entry['type'] = 'level'
                entry['name'] = info[1]
            elif len(info) == 3:
                entry['type'] = 'command'
                entry['level'] = info[1]
                entry['name'] = info[2]
        return entry

    def process(entry):
        'writes the entry into topics/levels/commands'
        short_help = entry['short']
        long_help = entry['long']
        if long_help.startswith('=='):
            long_help = long_help.split('\n', 1)[1]
        helpobj = HelpEntry(short_help, long_help.rstrip())
        name = entry['name']
        if entry['type'] == 'topic':
            _TOPICS[name] = helpobj
        elif entry['type'] == 'level':
            _LEVELS[name] = helpobj
        elif entry['type'] == 'command':
            lvl = entry['level']
            if lvl not in _COMMANDS:
                _COMMANDS[lvl] = odict()
            _COMMANDS[lvl][name] = helpobj

    def filter_line(line):
        '''clean up an input line
         - <<...>> references -> short description
         - remove surrounding dots from preformatted blocks
        '''
        line = _REFERENCE_RE.sub(r'\1', line)
        if re.match(r'^\.{3,}\n$', line):
            line = '\n'
        return line

    def append_cmdinfos():
        "append command information to level descriptions"
        for lvlname, level in _LEVELS.iteritems():
            if lvlname in _COMMANDS:
                level.long += "\n\nCommands:\n"
                for cmdname, cmd in _COMMANDS[lvlname].iteritems():
                    level.long += "\t`%-16s` %s\n" % (cmdname, cmd.short)

    try:
        name = os.getenv("CRM_HELP_FILE") or HELP_FILE
        helpfile = open(name, 'r')
        entry = None
        for line in helpfile:
            if line.startswith('[['):
                if entry is not None:
                    process(entry)
                entry = parse_header(line)
            elif entry is not None:
                entry['long'] += filter_line(line)
        helpfile.close()
        append_cmdinfos()
    except IOError, msg:
        common_err("%s open: %s" % (name, msg))
        common_err("extensive help system is not available")

# vim:ts=4:sw=4:et:
