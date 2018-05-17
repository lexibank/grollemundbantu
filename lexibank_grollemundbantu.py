# coding: utf8
from __future__ import unicode_literals
from collections import OrderedDict

from clldutils.misc import slug, lazyproperty
from clldutils.path import Path
from pylexibank.dataset import Dataset as BaseDataset
from lingpy.sequence.sound_classes import clean_string


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
    
    def clean_form(self, item, form):
        # Over ride clean_form to stop strip_brackets which messes lexemes like 
        # "(ku)tanga" up
        if form not in ['?']:
            return form
    
    @lazyproperty
    def tokenizer(self):
        return lambda x, y: clean_string_with_validation(y)

    def cmd_install(self, **kw):
        languages = {l['NAME']: l for l in self.languages}
        concepts = {
            x.english: (x.concepticon_id, x.concepticon_gloss) for x
            in self.conceptlist.concepts.values()
        }

        data = OrderedDict()

        # The english concept labels in the two excel sheets differ in one place:
        glosses = {'road/path': 'road'}

        header, rows = self.read_csv('Data')
        for row in rows:
            data[row[0]] = {
                'language': row[0],
                'source': row[-1],
                'objects': OrderedDict(zip(header[1:-2], row[1:-2])),
            }

        header, rows = self.read_csv('Multistate')
        for row in rows:
            ldata = data[row[0]]
            for j, csid in enumerate(row[1:]):
                concept = header[j + 1]
                try:
                    csid = '%s' % int(float(csid))
                except ValueError:
                    assert csid == '?'
                ldata['objects'][glosses.get(concept, concept)] = (
                    ldata['objects'][glosses.get(concept, concept)],
                    csid)
        
        # preprocess problematic lexemes
        self.lexemes = {  # wtf..
             k.encode('latin1', 'backslashreplace').decode('unicode-escape').lstrip(): v
             for (k, v) in self.lexemes.items()
        }
        
        with self.cldf as ds:
            ds.add_sources(*self.raw.read_bib())

            for lang in data.values():
                if not languages[lang['language']]:
                    self.unmapped.add_language(name=lang['language'])

                ds.add_language(
                    ID=slug(lang['language']),
                    Name=lang['language'],
                    Glottolog_Name=languages[lang['language']]['GLOTTOLOG_NAME'],
                    Glottocode=languages[lang['language']]['GLOTTOCODE'],
                    ISO639P3code=languages[lang['language']]['ISO'])

                for concept, item in lang['objects'].items():
                    if concept not in concepts:
                        self.unmapped.add_concept(id=slug(concept), name=concept)
                    if not item[0]:
                        continue
                    
                    cslug = slug(concept)
                    ds.add_concept(
                        ID=cslug,
                        Name=concept,
                        Concepticon_ID=concepts.get(concept)[0],
                        Concepticon_Gloss=concepts.get(concept)[1])
                    
                    for i, itm in enumerate(self.split_forms(item, item[0])):
                        # skip question marks and empty records
                        if itm == '?' or not itm:
                            continue
                        
                        # add cognate only to the first form
                        cogid = None
                        if i == 0 and item[1] != '?':
                            cogid = '%s-%s' % (cslug, item[1])
                        
                        for row in ds.add_lexemes(
                            Language_ID=slug(lang['language']),
                            Parameter_ID=cslug,
                            Value=itm,
                            Source=languages[lang['language']]['SOURCE'],
                            Cognacy=cogid if cogid else ''):
                            
                            if cogid:
                                ds.add_cognate(lexeme=row, Cognateset_ID=cogid)
