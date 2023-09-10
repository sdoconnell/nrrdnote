PREFIX = /usr/local
BINDIR = $(PREFIX)/bin
MANDIR = $(PREFIX)/share/man/man1
DOCDIR = $(PREFIX)/share/doc/nrrdnote
BSHDIR = /etc/bash_completion.d

.PHONY: all install uninstall

all:

install:
	install -m755 -d $(BINDIR)
	install -m755 -d $(MANDIR)
	install -m755 -d $(DOCDIR)
	install -m755 -d $(BSHDIR)
	gzip -c doc/nrrdnote.1 > nrrdnote.1.gz
	install -m755 nrrdnote/nrrdnote.py $(BINDIR)/nrrdnote
	install -m644 nrrdnote.1.gz $(MANDIR)
	install -m644 README.md $(DOCDIR)
	install -m644 CHANGES $(DOCDIR)
	install -m644 LICENSE $(DOCDIR)
	install -m644 CONTRIBUTING.md $(DOCDIR)
	install -m644 auto-completion/bash/nrrdnote-completion.bash $(BSHDIR)
	rm -f nrrdnote.1.gz

uninstall:
	rm -f $(BINDIR)/nrrdnote
	rm -f $(MANDIR)/nrrdnote.1.gz
	rm -f $(BSHDIR)/nrrdnote-completion.bash
	rm -rf $(DOCDIR)

