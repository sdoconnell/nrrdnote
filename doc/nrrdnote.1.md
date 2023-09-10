---
title: NRRDNOTE
section: 1
header: User Manual
footer: nrrdnote 0.0.2
date: January 3, 2022
---
# NAME
nrrdnote - Terminal-based note management for nerds.

# SYNOPSIS
**nrrdnote** *command* [*OPTION*]...

# DESCRIPTION
**nrrdnote** is a terminal-based note management program with advanced search options, and data stored in local text files. It can be run in either of two modes: command-line or interactive shell.

# OPTIONS
**-h**, **--help**
: Display help information.

**-c**, **--config** *file*
: Use a non-default configuration file.

# COMMANDS
**nrrdnote** provides the following commands.

**archive** *alias* [*OPTION*]
: Move a note to the archive directory of your data directory (by default, $HOME/.local/share/nrrdnote/archive). The user will be prompted for confirmation. Archiving a note removes it from all views, and is designed as a method to save old notes while removing them from **list** output.

    *OPTIONS*

    **-f**, **--force**
    : Force the archive operation, do not prompt for confirmation.

**config**
: Edit the **nrrdnote** configuration file.

**delete (rm)** *alias* [*OPTION*]
: Delete a note file. The user will be prompted for confirmation.

    *OPTIONS*

    **-f**, **--force**
    : Force deletion, do not prompt for confirmation.

**edit** *alias* [*OPTION*]...
: Edit or view a note (opens in $EDITOR, optionally with special options). If $EDITOR is not defined, an error message will report that.

    *OPTIONS*

    **-o**, **--editor-opts**
    : Special options to pass to the editor defined by $EDITOR.

**info** *alias* [*OPTION*]
: Show the full metadata about a note.

    *OPTIONS*

    **-p**, **--page**
    : Page the command output through $PAGER.

**list (ls)** *view* [*OPTION*]...
: List notes matching one of the following views:

    - *all* (*lsa*) : All notes in all notebooks.
    - *notebooks* (*lsn*) : A list of notebooks, with a count of contained notes.
    - \<*notebook*\> : All notes in a specific notebook.

    *OPTIONS*

    **-p**, **--page**
    : Page the command output through $PAGER.

**modify (mod)** *alias* [*OPTION*]...
: Modify the metadata for a note.

    *OPTIONS*

    **--new-alias** *alias*
    : Change the alias for a note.

    **--description** *description*
    : The note description.

    **--notebook** *notebook*
    : The notebook containing the note.

    **--tags** *tag*[,*tag*]
    : Tags assigned to the note. This can be a single tag or multiple tags in a comma-delimited list. Normally with this option, any existing tags assigned to the note will be replaced. However, this option also supports two special operators: **+** (add a tag to the existing tags) and **~** (remove a tag from the existing tags). For example, *--tags +documentation* will add the *documentation* tag to the existing tags on a note, and *--tags ~testing,experimental* will remove both the *testing* and *experimental* tags from a note.

    **--title** *title*
    : The note title.

**new** *title* [*OPTION*]...
: Create a new note.

    *OPTIONS*

    **--description**
    : The note description.

    **--notebook**
    : The notebook containing the note. A note created without a notebook will be placed in the default notebook (defined by the configuration parameter 'default_notebook').

    **--tags**
    : Tags assigned to the note. See the **--tags** option of **modify**.


**search** *searchterm* [*OPTION*]
: Search for one or more notes and output a tabular list (same format as **list**) with an excerpt of matching text. 

    *OPTIONS*

    **-p**, **--page**
    : Page the command output through $PAGER.


**shell**
: Launch the **nrrdnote** interactive shell.

**version**
: Show the application version information.

# NOTES

## Archiving a note
Use the **archive** subcommand to move the note file to the subdirectory archive in the the notes data directory. Confirmation will be required for this operation unless the *--force* option is also used.

Archived notes will no longer appear in lists of notes. This can be useful for retaining old notes without resulting in endlessly growing note lists. To review archived notes, create an alterate config file with a *data_dir* pointing to the archive folder, and an alias such as:

    alias nrrdnote-archive="nrrdnote -c $HOME/.config/nrrdnote/config.archive"

## Search
Search results are output in the same tabular, human-readable format as that of **list**, but also include excerpts for matching search results.

The most basic form of search is to simply search for a keyword or string in the note text:

    nrrdnote search <search_term>

A regular expression may be used to search note text by enclosing the term in "/" (i.e., "/\<regex to search for\>/").

Optionally, a search type may be specified. The search type may be one of *uid*, *alias*, *title*, *description*, *notebook*, *tags*, or *note*. If an invalid search type is provided, the search type will default to *note* (the note text). To specify a search type, use the format:

    nrrdnote search [search_type=]<search_term>

You may combine search types in a comma-delimited structure.

**Restrictions:**

    - The *note* type supports regular expression searches. However, use of a comma (,) in the regex itself will cause a failure in processing the search expression.

All other types perform case-insensitive, plain text searches.

The tags search type may also use the optional **+** operator to search for more than one tag. Any matched tag will return a result.

The special search term *any* can be used to match all notes, but is only useful in combination with an exclusion to match all records except those excluded.

## Exclusion
In addition to the search term, an exclusion term may be provided. Any match in the exclusion term will negate a match in the search term. An exclusion term is formatted in the same manner as the search term, must follow the search term, and must be denoted using the **%** operator:

    nrrdnote search [search_type=]<search_term>%[exclusion_type=]<exclusion_term>

The exclusion term may be a regular expression, following the same restrictions as for search. A regular expression exclusion can also be used in conjunction with a search term that includes search types.

## Search examples
Search for any note containing the word "projectx":

    nrrdnote search projectx

Search for any note containing the words "ProjectX", "ProjectY", or "ProjectZ", using a regular expression:

    nrrdnote search /Project[XYZ]/

The same search with an explicit *note* type:

    nrrdnote search note=/Project[XYZ]/

A similar search using an explicit *note* search is case-insensitive but can only search for "ProjectX":

    nrrdnote search note=projectx

Search for all notes tagged "development" or "testing" in the "Projects" notebook, except those that contain information about ProjectA or ProjectB:

    nrrdnote search notebook=Projects,tags=development+testing%/[Pp]roject[aAbB]/

## Paging
Output from **list** and **search** can get long and run past your terminal buffer. You may use the **-p** or **--page** option in conjunction with **search**, **info**, or **list** to page output.

# FILES
**~/.config/nrrdnote/config**
: Default configuration file

**~/.local/share/nrrdnote**
: Default data directory

# AUTHORS
Written by Sean O'Connell <https://sdoconnell.net>.

# BUGS
Submit bug reports at: <https://github.com/sdoconnell/nrrdnote/issues>

# SEE ALSO
Further documentation and sources at: <https://github.com/sdoconnell/nrrdnote>
