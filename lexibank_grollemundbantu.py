import pathlib
import collections
import attr
from clldutils.misc import slug
from pylexibank import Dataset as BaseDataset, Language as BaseLanguage
from pylexibank import FormSpec


@attr.s
class Language(BaseLanguage):
    Source = attr.ib(default=None)


class Dataset(BaseDataset):
    dir = pathlib.Path(__file__).parent
    id = "grollemundbantu"
    writer_options = dict(keep_languages=False, keep_parameters=False)
    language_class = Language
    DSET = "Grollemund-et-al_Bantu-database_2015"
    form_spec = FormSpec(
        separators="~,;/",
        # Don't mess up lexemes like "(ku)tanga"
        strip_inside_brackets=False,
        replacements=[(" ", "_"), ("-~ bilí", "bilí"), ("-́", "-"), ("-´", "-"),
                      ("-ː", "-"), ("_x001E_thathu", "thathu")],
        first_form_only=True,
        missing_data=["", "0.0", "?", "-", "- ", "0"],
    )

    def cmd_download(self, args):
        self.raw_dir.download_and_unpack(
            f"http://www.evolution.reading.ac.uk/Files/{self.DSET}.zip",
            self.DSET + ".xlsx",
            log=args.log,
        )
        self.raw_dir.xlsx2csv(self.DSET + ".xlsx")
        self.raw_dir.joinpath(self.DSET + ".xlsx").unlink()

    def read_csv(self, type_):
        header, rows = None, []
        for i, row in enumerate(
            self.raw_dir.read_csv(self.DSET + "." + type_ + ".csv")
        ):
            row = [c.strip() for c in row]
            if i == 2:
                header = row
            if i > 2:
                rows.append(row)
        return header, rows

    def cmd_makecldf(self, args):
        sources = {lang["Name"]: lang["Source"] for lang in self.languages}
        concepts = {
            x.english: (x.concepticon_id, x.concepticon_gloss)
            for x in self.conceptlists[0].concepts.values()
        }

        data = collections.OrderedDict()

        # The english concept labels in the two excel sheets differ in one place:
        glosses = {"road/path": "road"}

        header, rows = self.read_csv("Data")
        for row in rows:
            data[row[0]] = {
                "language": row[0],
                "source": row[-1],
                "objects": collections.OrderedDict(
                    zip(header[1:-2], row[1:-2])
                ),
            }

        header, rows = self.read_csv("Multistate")
        for row in rows:
            ldata = data[row[0]]
            for j, csid in enumerate(row[1:]):
                concept = header[j + 1]
                try:
                    csid = f"{int(float(csid))}"
                except ValueError:
                    assert csid == "?"
                ldata["objects"][glosses.get(concept, concept)] = (
                    ldata["objects"][glosses.get(concept, concept)],
                    csid,
                )

        args.writer.add_sources()
        languages = args.writer.add_languages(
            id_factory=lambda lang: slug(lang["Name"])
        )

        for _, lang in sorted(data.items()):
            if lang["language"] not in languages:
                self.unmapped.add_language(Name=lang["language"])

            for concept, item in sorted(lang["objects"].items()):
                if concept not in concepts:
                    self.unmapped.add_concept(id=slug(concept), name=concept)
                if not item[0]:
                    continue

                cslug = slug(concept)
                args.writer.add_concept(
                    ID=cslug,
                    Name=concept,
                    Concepticon_ID=concepts.get(concept)[0],
                    Concepticon_Gloss=concepts.get(concept)[1],
                )

                cogid = None
                if item[1] != "?":
                    cogid = f"{cslug}-{item[1]}"

                for i, row in enumerate(
                    args.writer.add_lexemes(
                        Language_ID=slug(lang["language"]),
                        Parameter_ID=cslug,
                        Value=item[0],
                        Source=sources[lang["language"]],
                        Cognacy=cogid if cogid else "",
                    )
                ):

                    # add cognate only to the first form
                    if cogid and i == 0:
                        args.writer.add_cognate(lexeme=row, Cognateset_ID=cogid)
