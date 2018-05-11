# coding: utf-8
from __future__ import unicode_literals


def test_valid(cldf_dataset, cldf_logger):
    assert cldf_dataset.validate(log=cldf_logger)


def test_forms(cldf_dataset, cldf_logger):  # SLOW

    def _get(parameter, language):
        return [
            f for f in cldf_dataset['FormTable']
            if f['Parameter_ID'] == parameter
            and f['Language_ID'] == language
        ]

    assert _get('elephant', 'fefegrassfields')[0]['Form'] =='sʉ̄ʉ'

    # Note: this test is time-consuming but Excel struggles to parse the csv
    # file for this language, so check it explicitly.
    assert _get('woman', 'b78wuumu')[0]['Form'] == 'mukáát'

    # E72a_Giryama, night was:
    # "baba	/ babayo	/ babaye	/ babiyehu	/ babiyenu baba mutu : a ..
    m = _get('night', 'e72agiryama')
    assert len(m) == 1, 'should only have one entry for E72a_Giryama/night'
    assert m[0]['Form'] == 'baba'


def test_no_empty_forms(cldf_dataset, cldf_logger):
    # incorrect parsing of the excel file lead to empty languages or
    # parameters. Check this is still not an issue.
    for f in cldf_dataset['FormTable']:
        assert f['Parameter_ID'] and f['Language_ID'], 'Missing info in %r' % f


# "We studied 424 language-cultural groups, of which 409 are Bantu-speaking,
# sampled from the whole Bantu area as described by Guthrie (64, 65)"
def test_languages(cldf_dataset, cldf_logger):
    assert len(list(cldf_dataset['LanguageTable'])) == 424


def test_sources(cldf_dataset, cldf_logger):
    assert len(cldf_dataset.sources) == 217


# "...we used a selection of 100 meanings..."
def test_parameters(cldf_dataset, cldf_logger):
    assert len(list(cldf_dataset['ParameterTable'])) == 100


# "We identified 3,859 cognate sets across the n = 100 meanings..."
def test_cognates(cldf_dataset, cldf_logger):
    cogsets = {c['Cognateset_ID'] for c in cldf_dataset['CognateTable']}
    assert len(cogsets) == 3859

