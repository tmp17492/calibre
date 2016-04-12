#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2016, Kovid Goyal <kovid at kovidgoyal.net>'

from functools import partial

from calibre.constants import iswindows
from calibre.ebooks.oeb.base import OEB_STYLES, OEB_DOCS
from calibre.ebooks.oeb.polish.cascade import iterrules, resolve_property, resolve_styles, DEFAULTS
from calibre.ebooks.oeb.polish.container import ContainerBase, href_to_name
from calibre.ebooks.oeb.polish.tests.base import BaseTest
from calibre.utils.logging import Log, Stream

class VirtualContainer(ContainerBase):

    tweak_mode = True

    def __init__(self, files):
        s = Stream()
        self.log_stream = s.stream
        log = Log()
        log.outputs = [s]
        ContainerBase.__init__(self, log=log)
        self.mime_map = {k:self.guess_type(k) for k in files}
        self.files = files

    def has_name(self, name):
        return name in self.mime_map

    def href_to_name(self, href, base=None):
        return href_to_name(href, ('C:\\root' if iswindows else '/root'), base)

    def parsed(self, name):
        if name not in self.parsed_cache:
            mt = self.mime_map[name]
            if mt in OEB_STYLES:
                self.parsed_cache[name] = self.parse_css(self.files[name], name)
            elif mt in OEB_DOCS:
                self.parsed_cache[name] = self.parse_xhtml(self.files[name], name)
            else:
                self.parsed_cache[name] = self.files[name]
        return self.parsed_cache[name]

class CascadeTest(BaseTest):

    def test_iterrules(self):
        def get_rules(files, name='x/one.css', l=1, rule_type=None):
            c = VirtualContainer(files)
            rules = tuple(iterrules(c, name, rule_type=rule_type))
            self.assertEqual(len(rules), l)
            return rules, c
        get_rules({'x/one.css':'@import "../two.css";', 'two.css':'body { color: red; }'})
        get_rules({'x/one.css':'@import "../two.css" screen;', 'two.css':'body { color: red; }'})
        get_rules({'x/one.css':'@import "../two.css" xyz;', 'two.css':'body { color: red; }'}, l=0)
        get_rules({'x/one.css':'@import "../two.css";', 'two.css':'body { color: red; }'}, l=0, rule_type='FONT_FACE_RULE')
        get_rules({'x/one.css':'@import "../two.css";', 'two.css':'body { color: red; }'}, rule_type='STYLE_RULE')
        get_rules({'x/one.css':'@media screen { body { color: red; } }'})
        get_rules({'x/one.css':'@media xyz { body { color: red; } }'}, l=0)
        c = get_rules({'x/one.css':'@import "../two.css";', 'two.css':'@import "x/one.css"; body { color: red; }'})[1]
        self.assertIn('Recursive import', c.log_stream.getvalue().decode('utf-8'))

    def test_resolve_styles(self):

        def test_property(select, style_map, selector, name, val=None):
            elem = next(select(selector))
            ans = resolve_property(elem, name, style_map)
            if val is None:
                val = type('')(DEFAULTS[name])
            self.assertEqual(val, ans.cssText)

        def get_maps(html, styles=None):
            html = '<html><head><link href="styles.css"></head><body>{}</body></html>'.format(html)
            c = VirtualContainer({'index.html':html, 'styles.css':styles or 'body { color: red }'})
            style_map, pseudo_style_map, select = resolve_styles(c, 'index.html')
            tp = partial(test_property, select, style_map)
            return tp

        t = get_maps('<p style="margin:11pt"><b>x</b>xx</p>')
        t('body', 'color', 'red')
        t('p', 'color', 'red')
        t('b', 'font-weight', 'bold')
        t('p', 'margin-top', '11pt')
        t('b', 'margin-top')
        t('body', 'display', 'block')
        t('b', 'display', 'inline')
        for e in ('body', 'p', 'b'):
            for prop in 'background-color text-indent'.split():
                t(e, prop)
