# coding: utf8
from __future__ import unicode_literals, print_function, division
from collections import OrderedDict
import re

from clldutils.misc import slug, lazyproperty
from clldutils.path import Path
from pylexibank.dataset import Metadata
from pylexibank.dataset import Dataset as BaseDataset
from lingpy.sequence.sound_classes import clean_string

from pylexibank.util import split_by_year, get_reference


def clean_string_with_validation(string):
    try:
        return clean_string(string)
    except IndexError:
        return []


class Dataset(BaseDataset):
    dir = Path(__file__).parent
    DSET = 'Grollemund-et-al_Bantu-database_2015'

    def cmd_download(self, **kw):
        self.raw.download_and_unpack(
            'http://www.evolution.reading.ac.uk/Files/%s.zip' % self.DSET,
            self.DSET + '.xlsx',
            log=self.log)
        self.raw.xls2csv(self.DSET + '.xlsx')
        self.raw.remove(self.DSET + '.xlsx')

    def read_csv(self, type_, **kw):
        header, rows = None, []
        for i, row in enumerate(self.raw.read_csv(self.DSET + '.' + type_ + '.csv')):
            row = [c.strip() for c in row]
            if i == 2:
                header = row
            if i > 2:
                rows.append(row)
        return header, rows

    def split_forms(self, row, value):
        return BaseDataset.split_forms(self, row, value.split('\n')[0])

    @lazyproperty
    def tokenizer(self):
        return lambda x, y: clean_string_with_validation(y)

    def cmd_install(self, **kw):
        language_map = {l['NAME']: l['GLOTTOCODE'] or None for l in self.languages}
        concept_map = {
            x.english: (x.concepticon_id, x.concepticon_gloss) for x
            in self.conceptlist.concepts.values()
        }

        data = OrderedDict()

        # The english concept labels in the two excel sheets differ in one place:
        gloss_map = {'road/path': 'road'}

        header, rows = self.read_csv('Data')
        for row in rows:
            data[row[0]] = {
                'language': row[0],
                'source': row[-1],
                'objects': OrderedDict(zip(header[1:-2], row[1:-2])),
            }

        ids = [slug(l['language']) for l in data.values()]
        assert len(set(ids)) == len(ids)

        header, rows = self.read_csv('Multistate')
        for row in rows:
            ldata = data[row[0]]
            for j, csid in enumerate(row[1:]):
                concept = header[j + 1]
                try:
                    csid = '%s' % int(float(csid))
                except ValueError:
                    assert csid == '?'
                ldata['objects'][gloss_map.get(concept, concept)] = (
                    ldata['objects'][gloss_map.get(concept, concept)],
                    csid)

        sources = {}
        with self.cldf as ds:
            for lang in data.values():
                if not language_map[lang['language']]:
                    self.unmapped.add_language(name=lang['language'])
                ref = ''
                if lang['source']:
                    ref = get_ref(lang, sources)
                    if ref:
                        ds.add_sources(ref.source)
                        ref = '%s' % ref

                ds.add_language(
                    ID=slug(lang['language']),
                    Name=lang['language'],
                    Glottocode=language_map[lang['language']])

                for concept, item in lang['objects'].items():
                    if concept not in concept_map:
                        self.unmapped.add_concept(id=slug(concept), name=concept)
                    if not item[0]:
                        continue

                    ds.add_concept(
                        ID=slug(concept),
                        Name=concept,
                        Concepticon_ID=concept_map.get(concept)[0],
                        Concepticon_Gloss=concept_map.get(concept)[1])

                    for row in ds.add_lexemes(
                            Language_ID=slug(lang['language']),
                            Parameter_ID=slug(concept),
                            Value=item[0],
                            Source=[ref],
                            Cognacy=item[1]):
                        if item[1] != '?':
                            ds.add_cognate(
                                lexeme=row,
                                Cognateset_ID='%s-%s' % (slug(concept), item[1]))

PAGES_PATTERN = re.compile('\s+p\.?\s*(?P<pages>[0-9]+)\.$')


def get_ref(lang, sources):
    pages = None
    src = lang['source'].strip()
    if src.startswith('Collectors:'):
        src = lang['source'].split('Collectors:')[1].strip()

    match = PAGES_PATTERN.search(src)
    if match:
        pages = match.group('pages')
        src = src[:match.start()].strip()

    author, year, src = split_by_year(src)
    return get_reference(author, year, src, pages, sources)
