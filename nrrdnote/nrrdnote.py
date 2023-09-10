#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nrrdnote
Version:  0.0.2
Author:   Sean O'Connell <sean@sdoconnell.net>
License:  MIT
Homepage: https://github.com/sdoconnell/nrrdnote
About:
A terminal-based notes management tool with local file-based storage.

usage: nrrdnote [-h] [-c <file>] for more help: nrrdnote <command> -h ...

Terminal-based notes management for nerds.

commands:
  (for more help: nrrdnote <command> -h)
    archive             archive a note
    delete (rm)         delete a note file
    edit                edit a note file (uses $EDITOR)
    info                show metadata about a note
    list (ls)           list notes
    modify (mod)        modify metadata for a note
    new                 create a new note
    search              search notes
    shell               interactive shell
    version             show version info

optional arguments:
  -h, --help            show this help message and exit
  -c <file>, --config <file>
                        config file

Copyright © 2021 Sean O'Connell

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

"""
import argparse
import configparser
import os
import random
import re
import shutil
import string
import subprocess
import sys
import time
import uuid
from cmd import Cmd
from datetime import datetime

import tzlocal
import yaml
from dateutil import parser as dtparser
from rich import box
from rich.color import ColorParseError
from rich.console import Console
from rich.padding import Padding
from rich.table import Table
from rich.text import Text
from rich.style import Style
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

APP_NAME = "nrrdnote"
APP_VERS = "0.0.2"
APP_COPYRIGHT = "Copyright © 2021 Sean O'Connell."
APP_LICENSE = "Released under MIT license."
DEFAULT_DATA_DIR = f"$HOME/.local/share/{APP_NAME}"
DEFAULT_CONFIG_FILE = f"$HOME/.config/{APP_NAME}/config"
DEFAULT_NOTEBOOK = "default"
DEFAULT_CONFIG = (
    "[main]\n"
    f"data_dir = {DEFAULT_DATA_DIR}\n"
    f"default_notebook = {DEFAULT_NOTEBOOK}\n"
    "# file extension for notes files (e.g. 'md' for\n"
    "# markdown. don't include the '.' character.\n"
    "# the default is no extension.\n"
    "#file_ext =\n"
    "# standard editor options to use when editing notes\n"
    "# may be overridden with -o/--editor-opts.\n"
    "#editor_options =\n"
    "\n"
    "[colors]\n"
    "disable_colors = false\n"
    "disable_bold = false\n"
    "# set to 'true' if your terminal pager supports color\n"
    "# output and you would like color output when using\n"
    "# the '--pager' ('-p') option\n"
    "color_pager = false\n"
    "# custom colors\n"
    "#table_title = blue\n"
    "#note_title = yellow\n"
    "#description = default\n"
    "#notebook = default\n"
    "#alias = bright_black\n"
    "#tags = cyan\n"
    "#label = white\n"
)


class Notes():
    """Performs note and notebook operations.

    Attributes:
        config_file (str):  application config file.
        data_dir (str):     directory containing note files.
        dflt_config (str):  the default config if none is present.

    """
    def __init__(
            self,
            config_file,
            data_dir,
            dflt_config):
        """Initializes an Notes() object."""
        self.config_file = config_file
        self.data_dir = data_dir
        self.config_dir = os.path.dirname(self.config_file)
        self.dflt_config = dflt_config
        self.interactive = False

        # default colors
        self.color_table_title = "bright_blue"
        self.color_note_title = "yellow"
        self.color_description = "default"
        self.color_notebook = "default"
        self.color_alias = "bright_black"
        self.color_tags = "cyan"
        self.color_label = "white"
        self.color_bold = True
        self.color_pager = False

        # editor (required for some functions)
        self.editor = os.environ.get("EDITOR")

        # defaults
        self.ltz = tzlocal.get_localzone()
        self.default_notebook = DEFAULT_NOTEBOOK
        self.file_ext = None
        self.editor_options = None

        # initial style definitions, these are updated after the config
        # file is parsed for custom colors
        self.style_table_title = None
        self.style_note_title = None
        self.style_description = None
        self.style_notebook = None
        self.style_alias = None
        self.style_tags = None
        self.style_label = None

        self._default_config()
        self._parse_config()
        self._verify_data_dir()
        self._parse_files()

    def _alias_not_found(self, alias):
        """Report an invalid alias and exit or pass appropriately.

        Args:
            alias (str):    the invalid alias.

        """
        self._handle_error(f"Alias '{alias}' not found")

    def _datetime_or_none(self, timestr):
        """Verify a datetime object or a datetime string in ISO format
        and return a datetime object or None.

        Args:
            timestr (str): a datetime formatted string.

        Returns:
            timeobj (datetime): a valid datetime object or None.

        """
        if isinstance(timestr, datetime):
            timeobj = timestr.astimezone(tz=self.ltz)
        else:
            try:
                timeobj = dtparser.parse(timestr).astimezone(tz=self.ltz)
            except (TypeError, ValueError, dtparser.ParserError):
                timeobj = None
        return timeobj

    def _default_config(self):
        """Create a default configuration directory and file if they
        do not already exist.
        """
        if not os.path.exists(self.config_file):
            try:
                os.makedirs(self.config_dir, exist_ok=True)
                with open(self.config_file, "w",
                          encoding="utf-8") as config_file:
                    config_file.write(self.dflt_config)
            except IOError:
                self._error_exit(
                    "Config file doesn't exist "
                    "and can't be created.")

    @staticmethod
    def _error_exit(errormsg):
        """Print an error message and exit with a status of 1

        Args:
            errormsg (str): the error message to display.

        """
        print(f'ERROR: {errormsg}.')
        sys.exit(1)

    @staticmethod
    def _error_pass(errormsg):
        """Print an error message but don't exit.

        Args:
            errormsg (str): the error message to display.

        """
        print(f'ERROR: {errormsg}.')

    def _format_note(self, uid, excerpt=None, notebook=False):
        """Format note block for a given alias.

        Args:
            uid (str):     the uid of the note to format.
            excerpt (str): search result excerpt.
            notebook (bool): include the notebook line.

        Returns:
            output (str):   the formatted output.

        """
        note = self._parse_note(uid)
        aliastxt = Text(f"({note['alias']})")
        aliastxt.stylize(self.style_alias)
        title = note['title']
        titletxt = Text(title)
        titletxt.stylize(self.style_note_title)
        description = note['description']
        if description:
            leadtxt = Text("\n   + ")
            labeltxt = Text("description:")
            labeltxt.stylize(self.style_label)
            descriptiontxt = Text(description)
            descriptiontxt.stylize(self.style_description)
            descr_line = Text.assemble(
                leadtxt,
                labeltxt,
                " ",
                descriptiontxt)
        else:
            descr_line = ""
        tags = note['tags']
        if tags:
            tags = ','.join(tags)
            leadtxt = Text("\n   + ")
            labeltxt = Text("tags:")
            labeltxt.stylize(self.style_label)
            tagtxt = Text(tags)
            tagtxt.stylize(self.style_tags)
            tag_line = Text.assemble(
                leadtxt,
                labeltxt,
                " ",
                tagtxt)
        else:
            tag_line = ""
        if excerpt:
            leadtxt = Text("\n   + ")
            labeltxt = Text("matches:")
            labeltxt.stylize(self.style_label)
            lines = excerpt.split('\n')
            block = ""
            for line in lines:
                block += f"\n     {line}"
                if line != lines[-1]:
                    block += "\n     ..."
            excerpttxt = Text(block)
            excerptline = Text.assemble(
                leadtxt,
                labeltxt,
                excerpttxt)
        else:
            excerptline = ""
        if notebook:
            leadtxt = Text("\n   + ")
            labeltxt = Text("notebook:")
            labeltxt.stylize(self.style_label)
            notebooktxt = Text(note['notebook'])
            notebooktxt.stylize(self.style_notebook)
            notebookline = Text.assemble(
                leadtxt,
                labeltxt,
                " ",
                notebooktxt)
        else:
            notebookline = ""
        output = Text.assemble(
            "- ",
            aliastxt,
            " ",
            titletxt,
            descr_line,
            notebookline,
            tag_line,
            excerptline)
        return output

    @staticmethod
    def _format_timestamp(timeobj, pretty=False):
        """Convert a datetime obj to a string.

        Args:
            timeobj (datetime): a datetime object.
            pretty (bool):      return a pretty formatted string.

        Returns:
            timestamp (str): "%Y-%m-%d %H:%M:%S" or "%Y-%m-%d[ %H:%M]".

        """
        if pretty:
            if timeobj.strftime("%H:%M") == "00:00":
                timestamp = timeobj.strftime("%Y-%m-%d")
            else:
                timestamp = timeobj.strftime("%Y-%m-%d %H:%M")
        else:
            timestamp = timeobj.strftime("%Y-%m-%d %H:%M:%S")
        return timestamp

    def _gen_alias(self):
        """Generates a new alias and check for collisions.

        Returns:
            alias (str):    a randomly-generated alias.

        """
        aliases = self._get_aliases()
        chars = string.ascii_lowercase + string.digits
        while True:
            alias = ''.join(random.choice(chars) for x in range(4))
            if alias not in aliases:
                break
        return alias

    def _get_aliases(self):
        """Generates a list of all note aliases.

        Returns:
            aliases (list): the list of all note aliases.

        """
        aliases = []
        for note in self.notes:
            alias = self.notes[note].get('alias')
            if alias:
                aliases.append(alias.lower())
        return aliases

    def _get_notebooks(self):
        """Generates a list of all notebooks.

        Returns:
            notebooks (list): the list of all notebooks.

        """
        notebooks = []
        for uid in self.notes:
            note = self._parse_note(uid)
            notebook = note.get('notebook')
            if notebook:
                if notebook not in notebooks:
                    notebooks.append(notebook)
        notebooks.sort()
        notebooks.insert(0, self.default_notebook)
        return notebooks

    def _handle_error(self, msg):
        """Reports an error message and conditionally handles error exit
        or notification.

        Args:
            msg (str):  the error message.

        """
        if self.interactive:
            self._error_pass(msg)
        else:
            self._error_exit(msg)

    def _parse_config(self):
        """Read and parse the configuration file."""
        config = configparser.ConfigParser()
        if os.path.isfile(self.config_file):
            try:
                config.read(self.config_file)
            except configparser.Error:
                self._error_exit("Error reading config file")

            if "main" in config:
                if config["main"].get("data_dir"):
                    self.data_dir = os.path.expandvars(
                        os.path.expanduser(
                            config["main"].get("data_dir")))

                self.default_notebook = config["main"].get(
                        "default_notebook", DEFAULT_NOTEBOOK)
                self.default_notebook = self.default_notebook.lower()

                self.file_ext = config["main"].get("file_ext")
                self.editor_options = config["main"].get("editor_options")

            def _apply_colors():
                """Try to apply custom colors and catch exceptions for
                invalid color names.
                """
                try:
                    self.style_table_title = Style(
                        color=self.color_table_title,
                        bold=self.color_bold)
                except ColorParseError:
                    pass
                try:
                    self.style_note_title = Style(
                        color=self.color_note_title)
                except ColorParseError:
                    pass
                try:
                    self.style_description = Style(
                        color=self.color_description)
                except ColorParseError:
                    pass
                try:
                    self.style_notebook = Style(
                        color=self.color_notebook,
                        bold=self.color_bold)
                except ColorParseError:
                    pass
                try:
                    self.style_alias = Style(
                        color=self.color_alias)
                except ColorParseError:
                    pass
                try:
                    self.style_tags = Style(
                        color=self.color_tags)
                except ColorParseError:
                    pass
                try:
                    self.style_label = Style(
                        color=self.color_label)
                except ColorParseError:
                    pass

            # apply default colors
            _apply_colors()

            if "colors" in config:
                # custom colors with fallback to defaults
                self.color_table_title = (
                    config["colors"].get(
                        "table_title", "bright_blue"))
                self.color_note_title = (
                    config["colors"].get(
                        "note_title", "yellow"))
                self.color_description = (
                    config["colors"].get(
                        "description", "default"))
                self.color_notebook = (
                    config["colors"].get(
                        "notebook", "default"))
                self.color_alias = (
                    config["colors"].get(
                        "alias", "bright_black"))
                self.color_tags = (
                    config["colors"].get(
                        "tags", "cyan"))
                self.color_label = (
                    config["colors"].get(
                        "label", "white"))

                # color paging (disabled by default)
                self.color_pager = config["colors"].getboolean(
                    "color_pager", "False")

                # disable colors
                if bool(config["colors"].getboolean("disable_colors")):
                    self.color_table_title = "default"
                    self.color_note_title = "default"
                    self.color_description = "default"
                    self.color_notebook = "default"
                    self.color_alias = "default"
                    self.color_tags = "default"
                    self.color_label = "default"

                # disable bold
                if bool(config["colors"].getboolean("disable_bold")):
                    self.color_bold = False

                # try to apply requested custom colors
                _apply_colors()
        else:
            self._error_exit("Config file not found")

    def _parse_files(self):
        """ Read notes files from `data_dir` and parse note data into
        `self.notes` object.

        Returns:
            notes (dict):    parsed data from each note file

        """
        this_note_files = {}
        this_notes = {}
        aliases = {}

        with os.scandir(self.data_dir) as entries:
            for entry in entries:
                read_entry = False
                if self.file_ext:
                    if (entry.name.endswith(f".{self.file_ext}") and
                            entry.is_file()):
                        fullpath = entry.path
                        read_entry = True
                else:
                    if entry.is_file():
                        fullpath = entry.path
                        read_entry = True
                if read_entry:
                    data = None
                    try:
                        with open(fullpath, "r",
                                  encoding="utf-8") as source:
                            notefile = source.read()
                            pattern = re.compile(r'---([\s\S]*?)---')
                            snip = pattern.search(notefile)
                            if snip:
                                header = snip[0]
                                header = "\n".join(header.split("\n")[:-1])
                                data = yaml.safe_load(header)
                                content = notefile.replace(snip[0], "")
                                if data:
                                    data['updated'] = self._datetime_or_none(
                                                time.ctime(
                                                    os.path.getmtime(entry)))
                                    data['path'] = fullpath
                                    data['note'] = content
                            else:
                                # no header data found
                                self._error_pass(
                                    f"failure reading or parsing {fullpath} "
                                    "- SKIPPING")
                    except (OSError, IOError, yaml.YAMLError):
                        self._error_pass(
                            f"failure reading or parsing {fullpath} "
                            "- SKIPPING")
                    if data:
                        uid = data.get("uid")
                        alias = data.get("alias")
                        add_note = True
                        if uid:
                            # duplicate UID detection
                            dupid = this_note_files.get(uid)
                            if dupid:
                                self._error_pass(
                                    "duplicate UID detected:\n"
                                    f"  {uid}\n"
                                    f"  {dupid}\n"
                                    f"  {fullpath}\n"
                                    f"SKIPPING {fullpath}")
                                add_note = False
                        if alias:
                            # duplicate alias detection
                            dupalias = aliases.get(alias)
                            if dupalias:
                                self._error_pass(
                                    "duplicate alias detected:\n"
                                    f"  {alias}\n"
                                    f"  {dupalias}\n"
                                    f"  {fullpath}\n"
                                    f"SKIPPING {fullpath}")
                                add_note = False
                        if add_note:
                            if alias and uid:
                                this_notes[uid] = data
                                this_note_files[uid] = fullpath
                                aliases[alias] = fullpath
                            else:
                                self._error_pass(
                                    "no uid and/or alias param "
                                    f"in {fullpath} - SKIPPING")
                    else:
                        self._error_pass(
                            f"no data in {fullpath} - SKIPPING")
        self.note_files = this_note_files.copy()
        self.notes = this_notes.copy()

    def _parse_note(self, uid):
        """Parse a note and return values for note parameters.

        Args:
            uid (str): the UUID of the note to parse.

        Returns:
            note (dict):    the note parameters.

        """
        note = {}
        note['uid'] = self.notes[uid].get('uid')

        note['created'] = self.notes[uid].get('created')
        if note['created']:
            note['created'] = self._datetime_or_none(note['created'])
        note['updated'] = self.notes[uid].get('updated')
        note['path'] = self.notes[uid].get('path')
        note['alias'] = self.notes[uid].get('alias')
        if note['alias']:
            note['alias'] = note['alias'].lower()

        note['title'] = self.notes[uid].get('title')
        note['description'] = self.notes[uid].get('description')
        note['notebook'] = self.notes[uid].get('notebook')
        if not note['notebook']:
            note['notebook'] = self.default_notebook
        else:
            note['notebook'] = note['notebook'].lower()
        note['tags'] = self.notes[uid].get('tags')
        note['note'] = self.notes[uid].get('note')

        return note

    def _perform_search(self, term):
        """Parses a search term and returns a list of matching notes.
        A 'term' can consist of two parts: 'search' and 'exclude'. The
        operator '%' separates the two parts. The 'exclude' part is
        optional.
        The 'search' and 'exclude' terms use the same syntax but differ
        in one noteable way:
          - 'search' is parsed as AND. All parameters must match to
        return a note record. Note that within a parameter the '+'
        operator is still an OR.
          - 'exclude' is parsed as OR. Any parameters that match will
        exclude a note record.

        Args:
            term (str):     the search term to parse.

        Returns:
            result_notes (list):   the notes matching the search criteria.

        """
        def _test_regex(term):
            """Test a search term and see if it's a regex.

            Args:
                term (str): the search term to test.

            Returns:
                regex (bool): is the term a regex.
                r_term (obj): compiled re object or the original term if
            not a regex.

            """
            # check to see if this is already a compiled regex pattern
            # e.g., if this was a naked regex search and we caught it
            # at the top already
            if isinstance(term, re.Pattern):
                regex = True
                r_term = term
            else:
                if term.startswith('/') and term.endswith('/'):
                    test_term = term[1:-1]
                    try:
                        valid_term = re.compile(test_term)
                    except re.error:
                        regex = False
                        r_term = term
                        self._error_pass(
                            "not a valid regex, falling back to "
                            "regular search")
                    else:
                        regex = True
                        r_term = valid_term
                else:
                    regex = False
                    r_term = term
            return regex, r_term

        # if the exclusion operator is in the provided search term then
        # split the term into two components: search and exclude
        # otherwise, treat it as just a search term alone.
        if "%" in term:
            term = term.split("%")
            searchterm = str(term[0])
            excludeterm = str(term[1])
        else:
            searchterm = str(term)
            excludeterm = None

        valid_criteria = [
            "uid=",
            "title=",
            "description=",
            "notebook=",
            "alias=",
            "tags=",
            "note="
        ]
        s_regex = False
        x_regex = False
        # parse the search term into a dict
        if searchterm:
            if searchterm.lower() == 'any':
                search = None
            elif not any(x in searchterm.lower() for x in valid_criteria):
                # treat this as a note search
                search = {}
                # see if the search term is a regex
                s_regex, s_term = _test_regex(searchterm)
                if s_regex:
                    search['note'] = s_term
                else:
                    search['note'] = s_term.strip()
            else:
                try:
                    search = dict((k.strip().lower(), v.strip())
                                  for k, v in (item.split('=')
                                  for item in searchterm.split(',')))
                except ValueError:
                    msg = "invalid search expression"
                    if not self.interactive:
                        self._error_exit(msg)
                    else:
                        self._error_pass(msg)
                        return
        else:
            search = None

        # parse the exclude term into a dict
        if excludeterm:
            if not any(x in excludeterm.lower() for x in valid_criteria):
                # treat this as a note search
                exclude = {}
                # see if the exclude term is a regex
                x_regex, x_term = _test_regex(excludeterm)
                if x_regex:
                    exclude['note'] = x_term
                else:
                    exclude['note'] = x_term.strip()
            else:
                try:
                    exclude = dict((k.strip().lower(), v.strip())
                                   for k, v in (item.split('=')
                                   for item in excludeterm.split(',')))
                except ValueError:
                    msg = "invalid exclude expression"
                    if not self.interactive:
                        self._error_exit(msg)
                    else:
                        self._error_pass(msg)
                        return
        else:
            exclude = None

        this_notes = self.notes.copy()
        exclude_list = []

        if exclude:
            x_uid = exclude.get('uid')
            x_alias = exclude.get('alias')
            x_title = exclude.get('title')
            x_description = exclude.get('description')
            x_notebook = exclude.get('notebook')
            x_tags = exclude.get('tags')
            if x_tags:
                x_tags = x_tags.split('+')
            x_note = exclude.get('note')
            if x_note:
                x_regex, x_note = _test_regex(x_note)

            for uid in this_notes:
                note = self._parse_note(uid)
                remove = False
                if x_uid:
                    if x_uid == uid:
                        remove = True
                if x_alias:
                    if note['alias']:
                        if x_alias.lower() == note['alias'].lower():
                            remove = True
                if x_title:
                    if note['title']:
                        if x_title.lower() in note['title'].lower():
                            remove = True
                if x_description:
                    if note['description']:
                        if (x_description.lower() in
                                note['description'].lower()):
                            remove = True
                if x_notebook:
                    if note['notebook']:
                        if x_notebook.lower() in note['notebook']:
                            remove = True
                if x_tags:
                    if note['tags']:
                        for tag in x_tags:
                            if (tag.lower() in [x.lower() for
                                                x in note['tags']]):
                                remove = True
                if x_note:
                    if note['note']:
                        contents = note['note'].split('\n')
                        for line in contents:
                            if x_regex:
                                r_match = re.search(x_note, line)
                                if r_match:
                                    remove = True
                            else:
                                if x_note.lower() in line.lower():
                                    remove = True
                if remove:
                    exclude_list.append(uid)

        # remove excluded notes
        for uid in exclude_list:
            this_notes.pop(uid)

        not_match = []

        if search:
            s_uid = search.get('uid')
            s_alias = search.get('alias')
            s_title = search.get('title')
            s_description = search.get('description')
            s_notebook = search.get('notebook')
            s_tags = search.get('tags')
            if s_tags:
                s_tags = s_tags.split('+')
            s_note = search.get('note')
            if s_note:
                s_regex, s_note = _test_regex(s_note)

            for uid in this_notes:
                note = self._parse_note(uid)
                remove = False
                if s_uid:
                    if not s_uid == uid:
                        remove = True
                if s_alias:
                    if note['alias']:
                        if not s_alias.lower() == note['alias'].lower():
                            remove = True
                    else:
                        remove = True
                if s_title:
                    if note['title']:
                        if (s_title.lower() not in
                                note['title'].lower()):
                            remove = True
                    else:
                        remove = True
                if s_description:
                    if note['description']:
                        if (s_description.lower() not in
                                note['description'].lower()):
                            remove = True
                    else:
                        remove = True
                if s_notebook:
                    if note['notebook']:
                        if (s_notebook.lower() not in
                                note['notebook']):
                            remove = True
                    else:
                        remove = True
                if s_tags:
                    keep = False
                    if note['tags']:
                        # searching for tags allows use of the '+' OR
                        # operator, so if we match any tag in the list
                        # then keep the entry
                        for tag in s_tags:
                            if (tag.lower() in [x.lower() for
                                                x in note['tags']]):
                                keep = True
                    if not keep:
                        remove = True
                if s_note:
                    if note['note']:
                        contents = note['note'].split('\n')
                        matches = []
                        for line in contents:
                            if s_regex:
                                r_match = re.search(s_note, line)
                                if r_match:
                                    matches.append(line.strip())
                            else:
                                if s_note.lower() in line.lower():
                                    matches.append(line.strip())
                        if matches:
                            this_notes[uid]['excerpt'] = '\n'.join(matches)
                        else:
                            remove = True
                    else:
                        remove = True
                if remove:
                    not_match.append(uid)

        # remove the notes that didn't match search criteria
        for uid in not_match:
            this_notes.pop(uid)

        result_notes = []
        for uid in this_notes:
            result_notes.append(this_notes[uid])

        return result_notes

    def _print_notebook_list(self, pager):
        """Print a list of all notebooks and a count of notes contained
        therein.

        Args:
            pager (bool):   paginate the output

        """
        notebooks = self._get_notebooks()
        notebook_stats = {}
        default_notebook = []
        for notebook in notebooks:
            notebook_stats[notebook] = 0
            for note in self.notes:
                alias = self.notes[note].get('alias')
                this_notebook = self.notes[note].get('notebook')
                if this_notebook:
                    if this_notebook.lower() == notebook:
                        notebook_stats[notebook] += 1
                else:
                    if alias not in default_notebook:
                        default_notebook.append(alias)
        notebook_stats[self.default_notebook] += len(default_notebook)
        console = Console()
        notebooks_table = Table(
            title="Notebooks",
            title_style=self.style_table_title,
            title_justify="left",
            box=box.SIMPLE,
            show_header=False,
            show_lines=False,
            pad_edge=False,
            collapse_padding=False,
            min_width=40,
            padding=(0, 0, 0, 0))
        # single column
        notebooks_table.add_column("column1")
        # add a row for each notebook with count
        for entry in notebook_stats:
            notebooktxt = Text(entry)
            notebooktxt.stylize(self.style_notebook)
            counttxt = Text(f"({notebook_stats[entry]})")
            line = Text.assemble(" - ", notebooktxt, " ", counttxt)
            notebooks_table.add_row(line)

        layout = Table.grid()
        layout.add_column("single")
        layout.add_row("")
        layout.add_row(notebooks_table)

        # render the output with a pager if --pager or -p
        if pager:
            if self.color_pager:
                with console.pager(styles=True):
                    console.print(layout)
            else:
                with console.pager():
                    console.print(layout)
        else:
            console.print(layout)

    def _print_note_list(
            self,
            notes,
            view,
            pager=False,
            excerpt=False,
            notebook=False):
        """Print the formatted notes list, sorted by notebook.

        Args:
            notes (list):   the list of notes (dicts) to be printed in a
        formatted manner.
            view (str):     the view name to display (notebook name or 'all').
            pager (bool):   paginate the output.
            excerpt (bool): show an excerpt from the note (used for search
        results).
            notebook (bool): show the notebook line (used for search results).

        """
        console = Console()
        notes_table = Table(
            title=f"Notes - {view}",
            title_style=self.style_table_title,
            title_justify="left",
            box=box.SIMPLE,
            show_header=False,
            show_lines=False,
            pad_edge=False,
            collapse_padding=False,
            min_width=40,
            padding=(0, 0, 0, 0))
        # single column
        notes_table.add_column("column1")

        if view.lower() == 'all':
            this_notebooks = []
            default_in_list = False
            # build a sorted list of notebooks, with default notebook first
            for note in notes:
                notebook = note['notebook']
                if notebook:
                    notebook = notebook.lower()
                if (notebook != self.default_notebook.lower() and
                        notebook not in this_notebooks):
                    this_notebooks.append(notebook)
                elif notebook == self.default_notebook:
                    default_in_list = True
            this_notebooks.sort()
            if default_in_list:
                this_notebooks.insert(0, self.default_notebook)
            current_notebook = None
            for notebook in this_notebooks:
                if current_notebook:
                    if notebook != current_notebook:
                        current_notebook = notebook
                        notes_table.add_row("")
                else:
                    current_notebook = notebook
                notes_in_notebook = {}
                for note in notes:
                    if note['notebook'] == notebook:
                        notes_in_notebook[note['uid']] = note['title']
                sort_by_title = dict(
                        sorted(notes_in_notebook.items(), key=lambda x: x[1]))
                notebooktxt = Text(notebook)
                notebooktxt.stylize(self.style_notebook)
                counttxt = Text(f"({len(notes_in_notebook)})")
                line = Text.assemble(" - ", notebooktxt, " ", counttxt)
                notes_table.add_row(line)
                for uid in sort_by_title:
                    this_note = self._format_note(uid)
                    notes_table.add_row(Padding(this_note, (0, 0, 0, 3)))
                    notes_table.add_row("")
        else:
            notes_in_list = {}
            excerpts = {}
            for note in notes:
                notes_in_list[note['uid']] = note['title']
                excerpt = note.get('excerpt')
                if excerpt:
                    excerpts[note['uid']] = excerpt
            sort_by_title = dict(
                    sorted(notes_in_list.items(), key=lambda x: x[1]))
            for uid in sort_by_title:
                if uid in excerpts:
                    excerpt = excerpts[uid]
                else:
                    excerpt = None
                this_note = self._format_note(
                        uid,
                        excerpt=excerpt,
                        notebook=notebook)
                notes_table.add_row(Padding(this_note, (0, 0, 0, 1)))
                notes_table.add_row("")
        if len(notes) == 0:
            notes_table.add_row(Text("None"))

        layout = Table.grid()
        layout.add_column("single")
        layout.add_row("")
        layout.add_row(notes_table)

        # render the output with a pager if --pager or -p
        if pager:
            if self.color_pager:
                with console.pager(styles=True):
                    console.print(layout)
            else:
                with console.pager():
                    console.print(layout)
        else:
            console.print(layout)

    def _uid_from_alias(self, alias):
        """Get the uid for a valid alias.

        Args:
            alias (str):    The alias of the note for which to find uid.

        Returns:
            uid (str or None): The uid that matches the submitted alias.

        """
        alias = alias.lower()
        uid = None
        for note in self.notes:
            this_alias = self.notes[note].get("alias")
            if this_alias:
                if this_alias == alias:
                    uid = note
        return uid

    def _verify_data_dir(self):
        """Create the notes data directory if it doesn't exist."""
        if not os.path.exists(self.data_dir):
            try:
                os.makedirs(self.data_dir)
            except IOError:
                self._error_exit(
                    f"{self.data_dir} doesn't exist "
                    "and can't be created")
        elif not os.path.isdir(self.data_dir):
            self._error_exit(f"{self.data_dir} is not a directory")
        elif not os.access(self.data_dir,
                           os.R_OK | os.W_OK | os.X_OK):
            self._error_exit(
                "You don't have read/write/execute permissions to "
                f"{self.data_dir}")

    @staticmethod
    def _write_note_file(metadata, filename, content=None):
        """Write YAML metadata to the top of a note file.

        Args:
            metadata (dict): the structured data to write.
            filename (str):  the location to write the data.
            content (str):   the note content.

        """
        with open(filename, "w",
                  encoding="utf-8") as out_file:
            out_file.write("---\n")
            yaml.dump(
                metadata,
                out_file,
                default_flow_style=False,
                sort_keys=False)
            out_file.write("---")
            if content:
                out_file.write(content)

    def archive(self, alias, force=False):
        """Archive a note identified by alias. Move the note to the
        {data_dir}/archive directory.

        Args:
            alias (str):    The alias of the note to be archived.
            force (bool):   Don't ask for confirmation before archiving.

        """
        archive_dir = os.path.join(self.data_dir, "archive")
        if not os.path.exists(archive_dir):
            try:
                os.makedirs(archive_dir)
            except OSError:
                msg = (
                    f"{archive_dir} doesn't exist and can't be created"
                )
                if not self.interactive:
                    self._error_exit(msg)
                else:
                    self._error_pass(msg)
                    return

        alias = alias.lower()
        uid = self._uid_from_alias(alias)
        if not uid:
            self._alias_not_found(alias)
        else:
            if force:
                confirm = "yes"
            else:
                confirm = input(f"Archive {alias}? [N/y]: ").lower()
            if confirm in ['yes', 'y']:
                filename = self.note_files.get(uid)
                if filename:
                    archive_file = os.path.join(
                        archive_dir, os.path.basename(filename))
                    try:
                        shutil.move(filename, archive_file)
                    except (IOError, OSError):
                        self._handle_error(f"failure moving {filename}")
                    else:
                        print(f"Archived note: {alias}")
                else:
                    self._handle_error(f"failed to find file for {alias}")
            else:
                print("Cancelled.")

    def delete(self, alias, force=False):
        """Delete a note identified by alias.

        Args:

            alias (str):    The alias of the note to be deleted.

        """
        alias = alias.lower()
        uid = self._uid_from_alias(alias)
        if not uid:
            self._alias_not_found(alias)
        else:
            filename = self.note_files.get(uid)
            if filename:
                if force:
                    confirm = "yes"
                else:
                    confirm = input(f"Delete '{alias}'? [yes/no]: ").lower()
                if confirm in ['yes', 'y']:
                    try:
                        os.remove(filename)
                    except OSError:
                        self._handle_error(f"failure deleting {filename}")
                    else:
                        print(f"Deleted note: {alias}")
                else:
                    print("Cancelled")
            else:
                self._handle_error(f"failed to find file for {alias}")

    def edit(self, alias, editor_opts=None):
        """Edit a note file identified by alias (using $EDITOR).

        Args:
            alias (str):    The alias of the note to be edited.
            editor_opts (str):  special options for $EDITOR command.

        """
        if self.editor:
            alias = alias.lower()
            uid = self._uid_from_alias(alias)
            if not uid:
                self._alias_not_found(alias)
            else:
                filename = self.note_files.get(uid)
                if filename:
                    if editor_opts:
                        editor_cmd = f"{self.editor} {editor_opts} {filename}"
                    elif self.editor_options:
                        editor_cmd = (
                            f"{self.editor} {self.editor_options} {filename}")
                    else:
                        editor_cmd = f"{self.editor} {filename}"
                    try:
                        subprocess.run(
                            editor_cmd,
                            check=True,
                            shell=True)
                    except subprocess.SubprocessError:
                        self._handle_error(
                            f"failure editing file {filename}")
                else:
                    self._handle_error(f"failed to find file for {alias}")
        else:
            self._handle_error("$EDITOR is required and not set")

    def edit_config(self):
        """Edit the config file (using $EDITOR) and then reload config."""
        if self.editor:
            try:
                subprocess.run(
                    [self.editor, self.config_file], check=True)
            except subprocess.SubprocessError:
                self._handle_error("failure editing config file")
            else:
                if self.interactive:
                    self._parse_config()
                    self.refresh()
        else:
            self._handle_error("$EDITOR is required and not set")

    def info(self, alias, pager=False):
        """Display metadata information for a note identified by alias.

        Args:
            alias (str):    The alias of the note to be diplayed.
            pager (bool):   Pipe output through console.pager.

        """
        console = Console()
        uid = self._uid_from_alias(alias)
        if not uid:
            self._alias_not_found(alias)
        else:
            note = self._parse_note(uid)

            info_table = Table(
                title=f"Note info - {alias}",
                title_style=self.style_table_title,
                title_justify="left",
                box=box.SIMPLE,
                show_header=False,
                show_lines=False,
                pad_edge=False,
                collapse_padding=False,
                min_width=40,
                padding=(0, 0, 0, 0))
            info_table.add_column("label", style=self.style_label)
            info_table.add_column("data")

            info_table.add_row("title:", note['title'])
            info_table.add_row("description:", note['description'])
            info_table.add_row("notebook:", note['notebook'])
            if note['tags']:
                tags = ','.join(note['tags'])
                info_table.add_row("tags:", tags)
            info_table.add_row("uid:", note['uid'])
            if note['created']:
                created = self._format_timestamp(note['created'])
                info_table.add_row("created:", created)
            if note['updated']:
                updated = self._format_timestamp(note['updated'])
                info_table.add_row("updated:", updated)
            info_table.add_row("file:", note['path'])
            layout = Table.grid()
            layout.add_column("single")
            layout.add_row("")
            layout.add_row(info_table)
            # render the output with a pager if --pager or -p
            if pager:
                if self.color_pager:
                    with console.pager(styles=True):
                        console.print(layout)
                else:
                    with console.pager():
                        console.print(layout)
            else:
                console.print(layout)

    def list(
            self,
            notebook,
            pager=None):
        """Prints a list of notes within a notebook, or a list of
        notebooks.

        Args:
            notebook (str): the notebook to view or 'notebooks' for a
        list of notebooks, or 'all' for all notes, arranged by notebook.
            pager (bool): paginate the output.

        """
        notebook = notebook.lower()
        if notebook == 'all':
            selected_notes = []
            for uid in self.notes:
                note = self._parse_note(uid)
                selected_notes.append(note)
            self._print_note_list(selected_notes, 'all', pager=pager)
        elif notebook == 'notebooks':
            self._print_notebook_list(pager=pager)
        elif notebook in self._get_notebooks():
            selected_notes = []
            for uid in self.notes:
                note = self._parse_note(uid)
                if note['notebook'] == notebook:
                    selected_notes.append(note)
            self._print_note_list(selected_notes, notebook, pager=pager)
        else:
            self._handle_error(
                f"no such notebook '{notebook}', check spelling")

    def modify(
            self,
            alias,
            new_alias=None,
            new_title=None,
            new_description=None,
            new_notebook=None,
            new_tags=None):
        """Modify a note's metadata using provided parameters.

        Args:
            alias(str):             the note alias being updated.
            new_alias (str):        new note alias.
            new_title (str):        new note title.
            new_description (str):  new note description.
            new_notebook (str):     new notebook for the note.
            new_tags (str):         new note tags.

        """
        alias = alias.lower()
        uid = self._uid_from_alias(alias)
        if not uid:
            self._alias_not_found(alias)
        else:
            filename = self.note_files.get(uid)
            aliases = self._get_aliases()
            note = self._parse_note(uid)

            if filename:
                created = note['created']
                if new_alias:
                    new_alias = new_alias.lower()
                    # duplicate alias check
                    aliases = self._get_aliases()
                    msg = f"alias '{alias}' already exists"
                    if new_alias in aliases and self.interactive:
                        self._error_pass(msg)
                        return
                    elif new_alias in aliases:
                        self._error_exit(msg)
                    else:
                        u_alias = new_alias
                else:
                    u_alias = alias
                u_title = new_title or note['title']
                u_description = new_description or note['description']
                if new_notebook:
                    if new_notebook.lower() in ['notebooks', 'all']:
                        msg = (
                            f"'{new_notebook}' is a reserved name and "
                            "cannot be used")
                        if self.interactive:
                            self._error_pass(msg)
                            return
                        else:
                            self._error_exit(msg)
                    else:
                        u_notebook = new_notebook.lower()
                else:
                    u_notebook = note['notebook']
                if new_tags:
                    new_tags = new_tags.lower()
                    if new_tags.startswith('+'):
                        new_tags = new_tags[1:]
                        new_tags = new_tags.split(',')
                        if not note['tags']:
                            tags = []
                        else:
                            tags = note['tags'].copy()
                        for new_tag in new_tags:
                            if new_tag not in tags:
                                tags.append(new_tag)
                        if tags:
                            tags.sort()
                            u_tags = tags
                        else:
                            u_tags = None
                    elif new_tags.startswith('~'):
                        new_tags = new_tags[1:]
                        new_tags = new_tags.split(',')
                        if note['tags']:
                            tags = note['tags'].copy()
                            for new_tag in new_tags:
                                if new_tag in tags:
                                    tags.remove(new_tag)
                            if tags:
                                tags.sort()
                                u_tags = tags
                            else:
                                u_tags = None
                        else:
                            u_tags = None
                    else:
                        u_tags = new_tags.split(',')
                        u_tags.sort()
                else:
                    u_tags = note['tags']
                metadata = {
                    "uid": uid,
                    "created": created,
                    "alias": u_alias,
                    "title": u_title,
                    "description": u_description,
                    "notebook": u_notebook,
                    "tags": u_tags
                }
                # write the updated file
                self._write_note_file(
                        metadata, filename, content=note['note'])

    def new(
            self,
            title=None,
            description=None,
            notebook=None,
            tags=None):
        """Create a new note.

        Args:
            title (str):        note title.
            description (str):  note description.
            notebook (str):     notebook containing the note.
            tags (str):         tags assigned to the note.

        """
        uid = str(uuid.uuid4())
        alias = self._gen_alias()
        now = datetime.now(tz=self.ltz)
        title_now = self._format_timestamp(now)
        title = title or f"New note - {title_now}"
        if notebook:
            notebook = notebook.lower()
        else:
            notebook = self.default_notebook
        if tags:
            tags = tags.lower()
            tags = tags.split(',')
            tags.sort()
        if notebook in ["notebooks", "all"]:
            self._handle_error(
                f"'{notebook}' is a reserved name and cannot be used")
        else:
            if self.file_ext:
                filename = os.path.join(
                        self.data_dir, f"{uid}.{self.file_ext}")
            else:
                filename = os.path.join(self.data_dir, uid)
            metadata = {
                "uid": uid,
                "created": now,
                "alias": alias,
                "title": title,
                "description": description,
                "notebook": notebook,
                "tags": tags
            }
            self._write_note_file(metadata, filename, content=None)
            print(f"Added note: {alias}")
            self.refresh()
            self.edit(alias)

    def new_note_wizard(self):
        """Prompt the user for note parameters and then call new()."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        title = input(f"Title [New note - {now}]: ") or f"New note - {now}"
        description = input("Description [none]: ") or None
        notebook = (input(f"Notebook (? for list) [{self.default_notebook}]: ")
                    or self.default_notebook)
        if notebook == "?":
            notebooks = self._get_notebooks()
            print("Notebooks:")
            valid_choices = []
            for index, nbname in enumerate(notebooks):
                print(f"  [{index+1}] {nbname}")
                valid_choices.append(index+1)
            choice = input("Choice [1]: ")
            try:
                choice = int(choice)
            except ValueError:
                pass
            if choice in valid_choices:
                notebook = notebooks[choice-1]
            else:
                notebook = notebooks[0]

        tags = input("Tags [none]: ") or None
        self.new(
            title=title,
            description=description,
            notebook=notebook,
            tags=tags)

    def refresh(self):
        """Public method to refresh data."""
        self._parse_files()

    def search(self, term, pager=False):
        """Perform a search for notes that match a given term and
        print the results in formatted text.

        Args:
            term (str):     the criteria for which to search.
            pager (bool):   whether to page output.

        """
        this_notes = self._perform_search(term)
        self._print_note_list(
                this_notes,
                'search results',
                pager,
                excerpt=True,
                notebook=True)


class FSHandler(FileSystemEventHandler):
    """Handler to watch for file changes and refresh data from files.
    Attributes:
        shell (obj):    the calling shell object.
    """
    def __init__(self, shell):
        """Initializes an FSHandler() object."""
        self.shell = shell

    def on_any_event(self, event):
        """Refresh data in memory on data file changes.
        Args:
            event (obj):    file system event.
        """
        if event.event_type in [
                'created', 'modified', 'deleted', 'moved']:
            self.shell.do_refresh("silent")


class NotesShell(Cmd):
    """Provides methods for interactive shell use.

    Attributes:
        notes (obj):     an instance of Notes().

    """
    def __init__(
            self,
            notes,
            completekey='tab',
            stdin=None,
            stdout=None):
        """Initializes a NotesShell() object."""
        super().__init__()
        self.notes = notes

        # start watchdog for data_dir changes
        # and perform refresh() on changes
        observer = Observer()
        handler = FSHandler(self)
        observer.schedule(
                handler,
                self.notes.data_dir,
                recursive=True)
        observer.start()

        # class overrides for Cmd
        if stdin is not None:
            self.stdin = stdin
        else:
            self.stdin = sys.stdin
        if stdout is not None:
            self.stdout = stdout
        else:
            self.stdout = sys.stdout
        self.cmdqueue = []
        self.completekey = completekey
        self.doc_header = (
            "Commands (for more info type: help):"
        )
        self.ruler = "―"

        self._set_prompt()

        self.nohelp = (
            "\nNo help for %s\n"
        )
        self.do_clear(None)

        print(
            f"{APP_NAME} {APP_VERS}\n\n"
            f"Enter command (or 'help')\n"
        )

    # class method overrides
    def default(self, args):
        """Handle command aliases and unknown commands.

        Args:
            args (str): the command arguments.

        """
        if args == "quit":
            self.do_exit("")
        elif args == "lsa":
            self.do_list("all")
        elif args == "lsa |":
            self.do_list("all |")
        elif args == "lsn":
            self.do_list("notebooks")
        elif args == "lsn |":
            self.do_list("notebooks |")
        elif args.startswith("ls"):
            newargs = args.split()
            if len(newargs) > 1:
                self.do_list(newargs[1])
            else:
                self.do_list("")
        elif args.startswith("rm"):
            newargs = args.split()
            if len(newargs) > 1:
                self.do_delete(newargs[1])
            else:
                self.do_delete("")
        elif args.startswith("mod"):
            newargs = args.split()
            if len(newargs) > 1:
                self.do_modify(newargs[1])
            else:
                self.do_modify("")
        else:
            print("\nNo such command. See 'help'.\n")

    def emptyline(self):
        """Ignore empty line entry."""

    def _set_prompt(self):
        """Set the prompt string."""
        if self.notes.color_bold:
            self.prompt = "\033[1mnotes\033[0m> "
        else:
            self.prompt = "notes> "

    def _uid_from_alias(self, alias):
        """Get the uid for a valid alias.

        Args:
            alias (str):    The alias of the note for which to find uid.

        Returns:
            uid (str or None): The uid that matches the submitted alias.

        """
        alias = alias.lower()
        uid = None
        for note in self.notes.notes:
            this_alias = self.notes.notes[note].get("alias")
            if this_alias:
                if this_alias == alias:
                    uid = note
        return uid

    @staticmethod
    def do_clear(args):
        """Clear the terminal.

        Args:
            args (str): the command arguments, ignored.

        """
        os.system("cls" if os.name == "nt" else "clear")

    def do_archive(self, args):
        """Archive a note.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            self.notes.archive(str(commands[0]).lower())
        else:
            self.help_archive()

    def do_config(self, args):
        """Edit the config file and reload the configuration.

        Args:
            args (str): the command arguments, ignored.

        """
        self.notes.edit_config()

    def do_delete(self, args):
        """Delete a note.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            self.notes.delete(str(commands[0]).lower())
        else:
            self.help_delete()

    def do_edit(self, args):
        """View or edit a note file via $EDITOR.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            self.notes.edit(str(commands[0]).lower())
        else:
            self.help_edit()

    @staticmethod
    def do_exit(args):
        """Exit the notes shell.

        Args:
            args (str): the command arguments, ignored.

        """
        sys.exit(0)

    def do_info(self, args):
        """Output metadata about a note.

        Args:
            args (str): the command arguments.

        """
        if len(args) > 0:
            alias = str(args).strip()
            if alias.endswith('|'):
                alias = alias[:-1].strip()
                page = True
            else:
                page = False
            self.notes.info(alias, page)
        else:
            self.help_info()

    def do_list(self, args):
        """Output a list of notebooks and notes.

        Args:
            args (str): the command arguments.

        """
        if len(args) > 0:
            notebook = str(args).strip()
            if notebook.endswith('|'):
                notebook = notebook[:-1].strip()
                page = True
            else:
                page = False
            self.notes.list(notebook, page)
        else:
            self.help_list()

    def do_modify(self, args):
        """Modify a note.
        Args:
            args (str): the command arguments.
        """
        if len(args) > 0:
            commands = args.split()
            alias = str(commands[0]).lower()
            uid = self._uid_from_alias(alias)
            if not uid:
                print(f"Alias '{alias}' not found")
            else:
                subshell = ModShell(self.notes, uid, alias)
                subshell.cmdloop()
        else:
            self.help_modify()

    def do_new(self, args):
        """Evoke the new note wizard.
        Args:
            args (str): the command arguments, ignored.
        """
        try:
            self.notes.new_note_wizard()
        except KeyboardInterrupt:
            print("\nCancelled.")

    def do_refresh(self, args):
        """Refresh entry information if files changed on disk.

        Args:
            args (str): the command arguments, ignored.

        """
        self.notes.refresh()
        if args != 'silent':
            print("Data refreshed.")

    def do_search(self, args):
        """Search for notes that meet certain criteria.

        Args:
            args (str): the command arguments.

        """
        if len(args) > 0:
            term = str(args).strip()
            if term.endswith('|'):
                term = term[:-1].strip()
                page = True
            else:
                page = False
            self.notes.search(term, page)
        else:
            self.help_search()

    @staticmethod
    def help_clear():
        """Output help for 'clear' command."""
        print(
            '\nclear:\n'
            '    Clear the terminal window.\n'
        )

    @staticmethod
    def help_config():
        """Output help for 'config' command."""
        print(
            '\nconfig:\n'
            '    Edit the config file with $EDITOR and then reload '
            'the configuration and refresh data files.\n'
        )

    @staticmethod
    def help_delete():
        """Output help for 'delete' command."""
        print(
            '\ndelete (rm) <alias>:\n'
            '    Delete a note file.\n'
        )

    @staticmethod
    def help_edit():
        """Output help for 'edit' command."""
        print(
            '\nedit <alias>:\n'
            '    View or edit a note file with $EDITOR.\n'
        )

    @staticmethod
    def help_exit():
        """Output help for 'exit' command."""
        print(
            '\nexit:\n'
            '    Exit the notes shell.\n'
        )

    @staticmethod
    def help_info():
        """Output help for 'info' command."""
        print(
            '\ninfo [|]:\n'
            '    Display details for the note. Add "|" as an'
            'argument to page the output.\n'
        )

    @staticmethod
    def help_list():
        """Output help for 'list' command."""
        print(
            '\nlist (ls) <notebook> [|]:\n'
            '    List notes in a notebook or \'all\' for all notes or '
            '\'notebooks\' for a list of all notebooks. Add \'|\' as a '
            'second argument to page the output.\n\n'
            '    The following command shortcuts are available:\n\n'
            '      lsa  : list all\n'
            '      lsn  : list notebooks\n'
        )

    @staticmethod
    def help_modify():
        """Output help for 'modify' command."""
        print(
            '\nmodify <alias>:\n'
            '    Modify a note file.\n'
        )

    @staticmethod
    def help_new():
        """Output help for 'new' command."""
        print(
            '\nnew:\n'
            '    Create new note interactively.\n'
        )

    @staticmethod
    def help_refresh():
        """Output help for 'refresh' command."""
        print(
            '\nrefresh:\n'
            '    Refresh the entry information from files on disk. '
            'This is useful if changes were made to files outside of '
            'the program shell (e.g. sync\'d from another computer).\n'
        )

    @staticmethod
    def help_search():
        """Output help for 'search' command."""
        print(
            '\nsearch <term> [|]:\n'
            '    Search for a note or notes that meet some specified '
            'criteria. Add \'|\' as a second argument to page the '
            'output.\n'
        )


class ModShell(Cmd):
    """Subshell for modifying a note.

    Attributes:
        notes (obj):    an instance of Notes().
        uid (str):      the uid of the note being modified.
        alias (str):    the alias of the note being modified.

    """
    def __init__(
            self,
            notes,
            uid,
            alias,
            completekey='tab',
            stdin=None,
            stdout=None):
        """Initializes a ModShell() object."""
        super().__init__()
        self.notes = notes
        self.uid = uid
        self.alias = alias

        # class overrides for Cmd
        if stdin is not None:
            self.stdin = stdin
        else:
            self.stdin = sys.stdin
        if stdout is not None:
            self.stdout = stdout
        else:
            self.stdout = sys.stdout
        self.cmdqueue = []
        self.completekey = completekey
        self.doc_header = (
            "Commands (for more info type: help):"
        )
        self.ruler = "―"

        self._set_prompt()

        self.nohelp = (
            "\nNo help for %s\n"
        )

    # class method overrides
    def default(self, args):
        """Handle command aliases and unknown commands.

        Args:
            args (str): the command arguments.

        """
        if args.startswith("quit") or args.startswith("exit"):
            return True
        else:
            print("\nNo such command. See 'help'.\n")

    @staticmethod
    def emptyline():
        """Ignore empty line entry."""

    @staticmethod
    def _error_pass(errormsg):
        """Print an error message but don't exit.
        Args:
            errormsg (str): the error message to display.
        """
        print(f'ERROR: {errormsg}.')

    def _get_aliases(self):
        """Generates a list of all note aliases.

        Returns:
            aliases (list): the list of all note aliases.

        """
        aliases = []
        for note in self.notes.notes:
            alias = self.notes.notes[note].get('alias')
            if alias:
                aliases.append(alias.lower())
        return aliases

    def _set_prompt(self):
        """Set the prompt string."""
        if self.notes.color_bold:
            self.prompt = f"\033[1mmodify ({self.alias})\033[0m> "
        else:
            self.prompt = f"modify ({self.alias})> "

    def do_alias(self, args):
        """Change the alias of a note.
        Args:
            args (str): the command arguments.
        """
        commands = args.split()
        if len(commands) > 0:
            aliases = self._get_aliases()
            newalias = str(commands[0]).lower()
            if newalias in aliases:
                self._error_pass(
                        f"alias '{newalias}' already in use")
            else:
                self.notes.modify(
                    alias=self.alias,
                    new_alias=newalias)
                self.alias = newalias
                self._set_prompt()
        else:
            self.help_alias()

    @staticmethod
    def do_clear(args):
        """Clear the terminal.

        Args:
            args (str): the command arguments, ignored.

        """
        os.system("cls" if os.name == "nt" else "clear")

    def do_description(self, args):
        """Modify the description on a note.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            description = str(args)
            self.notes.modify(
                alias=self.alias,
                new_description=description)
        else:
            self.help_description()

    @staticmethod
    def do_done(args):
        """Exit the modify subshell.

        Args:
            args (str): the command arguments, ignored.

        """
        return True

    def do_info(self, args):
        """Display full details for the selected note.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            commands = args.split()
            if str(commands[0]) == "|":
                self.notes.info(self.alias, True)
            else:
                self.notes.info(self.alias)
        else:
            self.notes.info(self.alias)

    def do_notebook(self, args):
        """Modify the notebook for a note.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            notebook = str(args)
            self.notes.modify(
                alias=self.alias,
                new_notebook=notebook)
        else:
            self.help_notebook()

    def do_tags(self, args):
        """Modify the tags on a note.
        Args:
            args (str):     the command arguments.
        """
        if len(args) > 0:
            commands = args.split()
            tags = str(commands[0])
            self.notes.modify(
                alias=self.alias,
                new_tags=tags)
        else:
            self.help_tags()

    def do_title(self, args):
        """Modify the title of a note.

        Args:
            args (str):     the command arguments.

        """
        if len(args) > 0:
            title = str(args)
            self.notes.modify(
                alias=self.alias,
                new_title=title)
        else:
            self.help_title()

    @staticmethod
    def help_alias():
        """Output help for 'alias' command."""
        print(
            '\nalias <new alias>:\n'
            '    Change the alias of the note.\n'
        )

    @staticmethod
    def help_clear():
        """Output help for 'clear' command."""
        print(
            '\nclear:\n'
            '    Clear the terminal window.\n'
        )

    @staticmethod
    def help_description():
        """Output help for 'description' command."""
        print(
            '\ndescription <description>:\n'
            '    Modify the description of this note.\n'
        )

    @staticmethod
    def help_done():
        """Output help for 'done' command."""
        print(
            '\ndone:\n'
            '    Finish modifying the task.\n'
        )

    @staticmethod
    def help_info():
        """Output help for 'info' command."""
        print(
            '\ninfo [|]:\n'
            '    Display details for the note. Add "|" as an'
            'argument to page the output.\n'
        )

    @staticmethod
    def help_notebook():
        """Output help for 'notebook' command."""
        print(
            '\nnotebook <notebook>:\n'
            '    Modify the notebook of this note.\n'
        )

    @staticmethod
    def help_tags():
        """Output help for 'tags' command."""
        print(
            '\ntags <tag>[,tag]:\n'
            '    Modify the tags on this note. A comma-delimted list or '
            'you may use the + and ~ notations to add or delete a tag '
            'from the existing tags.\n'
        )

    @staticmethod
    def help_title():
        """Output help for 'title' command."""
        print(
            '\ntitle <title>:\n'
            '    Modify the title of this note.\n'
        )


def parse_args():
    """Parse command line arguments.

    Returns:
        args (dict):    the command line arguments provided.

    """
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description='Terminal-based notes management for nerds.')
    parser._positionals.title = 'commands'
    parser.set_defaults(command=None)
    subparsers = parser.add_subparsers(
        metavar=f'(for more help: {APP_NAME} <command> -h)')
    pager = subparsers.add_parser('pager', add_help=False)
    pager.add_argument(
        '-p',
        '--page',
        dest='page',
        action='store_true',
        help="page output")
    archive = subparsers.add_parser(
        'archive',
        help='archive a note')
    archive.add_argument(
        'alias',
        help='note alias')
    archive.add_argument(
        '-f',
        '--force',
        dest='force',
        action='store_true',
        help="archive without confirmation")
    archive.set_defaults(command='archive')
    config = subparsers.add_parser(
        'config',
        help='edit configuration file')
    config.set_defaults(command='config')
    delete = subparsers.add_parser(
        'delete',
        aliases=['rm'],
        help='delete a note file')
    delete.add_argument(
        'alias',
        help='note alias')
    delete.add_argument(
        '-f',
        '--force',
        dest='force',
        action='store_true',
        help="delete without confirmation")
    delete.set_defaults(command='delete')
    edit = subparsers.add_parser(
        'edit',
        help='edit a note file (uses $EDITOR)')
    edit.add_argument(
        'alias',
        help='note alias')
    edit.add_argument(
        '-o',
        '--editor-opts',
        metavar="<options>",
        dest='editor_opts',
        help='$EDITOR options')
    edit.set_defaults(command='edit')
    info = subparsers.add_parser(
        'info',
        parents=[pager],
        help='show metadata about a note')
    info.add_argument(
        'alias',
        help='the note to view')
    info.set_defaults(command='info')
    listcmd = subparsers.add_parser(
        'list',
        parents=[pager],
        aliases=['ls'],
        help='list notes')
    listcmd.add_argument(
        'notebook',
        help='list notes in notebook (or \'all\')')
    listcmd.set_defaults(command='list')
    # list shortcuts
    lsa = subparsers.add_parser('lsa', parents=[pager])
    lsa.set_defaults(command='lsa')
    lsn = subparsers.add_parser('lsn', parents=[pager])
    lsn.set_defaults(command='lsn')
    modify = subparsers.add_parser(
        'modify',
        aliases=['mod'],
        help='modify metadata for a note')
    modify.add_argument(
        'alias',
        help='the note to modify')
    modify.add_argument(
        '--new-alias',
        metavar='<alias>',
        dest='new_alias',
        help='a new alias for the note')
    modify.add_argument(
        '--description',
        metavar='<description>',
        help='note description')
    modify.add_argument(
        '--notebook',
        metavar='<notebook>',
        help='notebook containing the note')
    modify.add_argument(
        '--tags',
        metavar='<tag>[,tag]',
        help='note tag(s)')
    modify.add_argument(
        '--title',
        metavar='<title>',
        help='note title')
    modify.set_defaults(command='modify')
    new = subparsers.add_parser(
        'new',
        help='create a new note')
    new.add_argument(
        'title',
        help='note title')
    new.add_argument(
        '--description',
        metavar='<description>',
        help='note description')
    new.add_argument(
        '--notebook',
        metavar='<notebook>',
        help='note notebook')
    new.add_argument(
        '--tags',
        metavar='<tag>[,tag]',
        help='note tag(s)')
    new.set_defaults(command='new')
    search = subparsers.add_parser(
        'search',
        parents=[pager],
        help='search notes')
    search.add_argument(
        'term',
        help='search term')
    search.set_defaults(command='search')
    shell = subparsers.add_parser(
        'shell',
        help='interactive shell')
    shell.set_defaults(command='shell')
    version = subparsers.add_parser(
        'version',
        help='show version info')
    version.set_defaults(command='version')
    parser.add_argument(
        '-c',
        '--config',
        dest='config',
        metavar='<file>',
        help='config file')
    args = parser.parse_args()
    return parser, args


def main():
    """Entry point. Parses arguments, creates Notes() object, calls
    requested method and parameters.
    """
    if os.environ.get("XDG_CONFIG_HOME"):
        config_file = os.path.join(
            os.path.expandvars(os.path.expanduser(
                os.environ["XDG_CONFIG_HOME"])), APP_NAME, "config")
    else:
        config_file = os.path.expandvars(
            os.path.expanduser(DEFAULT_CONFIG_FILE))

    if os.environ.get("XDG_DATA_HOME"):
        data_dir = os.path.join(
            os.path.expandvars(os.path.expanduser(
                os.environ["XDG_DATA_HOME"])), APP_NAME)
    else:
        data_dir = os.path.expandvars(
            os.path.expanduser(DEFAULT_DATA_DIR))

    parser, args = parse_args()

    if args.config:
        config_file = os.path.expandvars(
            os.path.expanduser(args.config))

    notes = Notes(
        config_file,
        data_dir,
        DEFAULT_CONFIG)

    if not args.command:
        parser.print_help(sys.stderr)
        sys.exit(1)
    elif args.command == "archive":
        notes.archive(args.alias, args.force)
    elif args.command == "config":
        notes.edit_config()
    elif args.command == "delete":
        notes.delete(args.alias, args.force)
    elif args.command == "info":
        notes.info(args.alias,
                   pager=args.page)
    elif args.command == "list":
        notes.list(args.notebook,
                   pager=args.page)
    elif args.command == "lsa":
        notes.list("all",
                   pager=args.page)
    elif args.command == "lsn":
        notes.list("notebooks",
                   pager=args.page)
    elif args.command == "modify":
        notes.modify(
            alias=args.alias,
            new_alias=args.new_alias,
            new_title=args.title,
            new_description=args.description,
            new_notebook=args.notebook,
            new_tags=args.tags)
    elif args.command == "new":
        notes.new(
            title=args.title,
            description=args.description,
            notebook=args.notebook,
            tags=args.tags)
    elif args.command == "edit":
        notes.edit(args.alias, editor_opts=args.editor_opts)
    elif args.command == "search":
        notes.search(args.term, args.page)
    elif args.command == "shell":
        notes.interactive = True
        shell = NotesShell(notes)
        shell.cmdloop()
    elif args.command == "version":
        print(f"{APP_NAME} {APP_VERS}")
        print(APP_COPYRIGHT)
        print(APP_LICENSE)
    else:
        sys.exit(1)


# entry point
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(1)
