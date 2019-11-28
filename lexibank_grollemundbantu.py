import pathlib
import collections

from clldutils.misc import slug, lazyproperty
import attr

from pylexibank import Dataset as BaseDataset, Language as BaseLanguage
from pylexibank import FormSpec
from lingpy.sequence.sound_classes import clean_string


@attr.s
class Language(BaseLanguage):
    Source = attr.ib(default=None)


def clean_string_with_validation(kw, string):
    try:
        return clean_string(string)[0].split()
    except IndexError:
        return []


class Dataset(BaseDataset):
    dir = pathlib.Path(__file__).parent
    id = 'grollemundbantu'
    language_class = Language
    DSET = 'Grollemund-et-al_Bantu-database_2015'
    form_spec = FormSpec(
        # Don't mess up lexemes like  "(ku)tanga"
        strip_inside_brackets=False,
    )

    def cmd_download(self, args):
        self.raw_dir.download_and_unpack(
            'http://www.evolution.reading.ac.uk/Files/%s.zip' % self.DSET,
            self.DSET + '.xlsx',
            log=args.log)
        self.raw_dir.xls2csv(self.DSET + '.xlsx')
        self.raw_dir.joinpath(self.DSET + '.xlsx').unlink()

    def read_csv(self, type_, **kw):
        header, rows = None, []
        for i, row in enumerate(self.raw_dir.read_csv(self.DSET + '.' + type_ + '.csv')):
            row = [c.strip() for c in row]
            if i == 2:
                header = row
            if i > 2:
                rows.append(row)
        return header, rows

    @lazyproperty
    def tokenizer(self):
        return clean_string_with_validation

    def cmd_makecldf(self, args):
        sources = {l['Name']: l['Source'] for l in self.languages}
        concepts = {
            x.english: (x.concepticon_id, x.concepticon_gloss) for x
            in self.conceptlists[0].concepts.values()
        }

        data = collections.OrderedDict()

        # The english concept labels in the two excel sheets differ in one place:
        glosses = {'road/path': 'road'}

        header, rows = self.read_csv('Data')
        for row in rows:
            data[row[0]] = {
                'language': row[0],
                'source': row[-1],
                'objects': collections.OrderedDict(zip(header[1:-2], row[1:-2])),
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

        args.writer.add_sources()
        languages = args.writer.add_languages(id_factory=lambda l: slug(l['Name']))

        for _, lang in sorted(data.items()):
            if lang['language'] not in languages:
                self.unmapped.add_language(Name=lang['language'])

            for concept, item in sorted(lang['objects'].items()):
                if concept not in concepts:
                    self.unmapped.add_concept(id=slug(concept), name=concept)
                if not item[0]:
                    continue

                cslug = slug(concept)
                args.writer.add_concept(
                    ID=cslug,
                    Name=concept,
                    Concepticon_ID=concepts.get(concept)[0],
                    Concepticon_Gloss=concepts.get(concept)[1])

                cogid = None
                if item[1] != '?':
                    cogid = '%s-%s' % (cslug, item[1])

                for i, row in enumerate(args.writer.add_lexemes(
                    Language_ID=slug(lang['language']),
                    Parameter_ID=cslug,
                    Value=item[0],
                    Source=sources[lang['language']],
                    Cognacy=cogid if cogid else '')):

                    # add cognate only to the first form
                    if cogid and i == 0:
                        args.writer.add_cognate(lexeme=row, Cognateset_ID=cogid)
