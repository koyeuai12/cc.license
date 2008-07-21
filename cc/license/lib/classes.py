import RDF
import zope.interface
import interfaces 
import rdf_helper

import cc.license
from cc.license.lib.exceptions import NoValuesFoundError, CCLicenseError
from cc.license.jurisdictions import uri2code

class License(object):
    """Base class for ILicense implementation modeling a specific license."""
    zope.interface.implements(interfaces.ILicense)

    def __init__(self, model, uri, license_class):
        self._uri = uri
        self._model = model # hang on to the model for lazy queries later
        self._lclass = license_class # defined by Selector
        self._titles = None
        self._descriptions = None
        self._superseded_by = None
        self._version = None
        self._jurisdiction = None
        self._deprecated = None
        self._superseded = None

        # make sure the license actually exists
        qstring = """
                  PREFIX cc: <http://creativecommons.org/ns#>
                  PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                
                  ASK { <%s> rdf:type cc:License . }"""
        query = RDF.Query(qstring % self.uri, query_language='sparql')
        uri_exists = query.execute(model).get_boolean()
        if not uri_exists:
            raise CCLicenseError, \
                  "License <%s> does not exist in model given." % self.uri

    def title(self, language='en'):
        if self._titles is None:
            self._titles = rdf_helper.get_titles(self._model, self.uri)
        return self._titles[language]

    def description(self, language='en'):
        if self._descriptions is None:
            self._descriptions = rdf_helper.get_descriptions(
                                           self._model, self.uri)
        if self._descriptions == '':
            return ''
        else:
            return self._descriptions[language]

    @property
    def license_class(self):
        return self._lclass

    # XXX use distutils.version.StrictVersion to ease comparison?
    # XXX return what if nonexistent?
    @property
    def version(self):
        if self._version is None:
            self._version = rdf_helper.get_version(self._model, self.uri)
        return self._version

    # XXX return what if nonexistent?
    @property
    def jurisdiction(self):
        if self._jurisdiction is None:
            self._jurisdiction = rdf_helper.get_jurisdiction(self._model, self.uri)
        return self._jurisdiction

    @property
    def uri(self):
        return self._uri

    @property
    def current_version(self):
        j = None
        if self.jurisdiction != '':
            j = cc.license.jurisdictions.uri2code(self.jurisdiction.id)
        return cc.license.lib.current_version(self.license_code, j)

    @property
    def deprecated(self):
        if self._deprecated is None:
            self._deprecated = rdf_helper.get_deprecated(self._model, self.uri)
        return self._deprecated

    @property
    def superseded(self):
        if self._superseded is None:
            self._superseded, self._superseded_by = \
                            rdf_helper.get_superseded(self._model, self.uri)
            # just in case superseded_by is needed down the line
        return self._superseded

    @property
    def license_code(self):
        return cc.license.lib.code_from_uri(self.uri)

    # TODO: implement!
    # TODO: write tests!
    @property
    def libre(self):
        return False


class Question(object):
    zope.interface.implements(interfaces.IQuestion)

    def __init__(self, root, lclass, id):
        """Given an etree root object, a license class string, and a question
           identifier string, populate this Question object with all
           relevant data found in the etree."""
        self._id = id

        _flag = False # for error checking
        # xml:lang namespace
        xlang = '{http://www.w3.org/XML/1998/namespace}lang'

        for child in root.getchildren():
            if child.get('id') != lclass:
                continue
            for field in child.findall('field'):
                if field.get('id') != self.id:
                    continue
                _flag = True # throw error if we don't find our lclass and id
                self._labels = {}
                self._descs = {}
                self._enums = {}
                for l in field.findall('label'):
                    self._labels[l.get(xlang)] = l.text
                for d in field.findall('description'):
                    self._descs[d.get(xlang)] = d.text
                for e in field.findall('enum'):
                    eid = e.get('id')
                    elabels = {}
                    for l in e.findall('label'):
                        elabels[l.get(xlang)] = l.text
                    self._enums[eid] = elabels

        if not _flag:
            raise CCLicenseError, "Question identifier %s not found" % self.id
            
    @property
    def id(self):
        return self._id

    def label(self, language='en'):
        if language == '':
            language = 'en' # why not?
        return self._labels[language]

    def description(self, language='en'):
        if language == '':
            language = 'en' # why not?
        return self._descs[language]

    def answers(self, language='en'):
        if language == '':
            language = 'en' # why not?
        return [ ( self._enums[k][language], k ) 
                 for k in self._enums.keys() ]


class LicenseSelector:
    zope.interface.implements(interfaces.ILicenseSelector)

    def __init__(self, uri, license_code):
        """Generates a LicenseSelector instance from a given URI.
           First it parses the RDF to get all information in there.
           Then it has to go to questions.xml to get the rest.
           In the questions.xml is soon to be deprecated, with all
           that information moving to RDF."""
        self._uri = uri
        self._id = license_code
        self._titles = rdf_helper.get_titles(rdf_helper.SEL_MODEL, self.uri)
        self._model = rdf_helper.ALL_MODEL # room for optimization...
        self._licenses = {}

    @property
    def uri(self):
        return self._uri

    @property
    def id(self):
        return self._id

    def title(self, language='en'):
        return self._titles[language]

    def by_uri(self, uri):
        if uri not in self._licenses:
            self._licenses[uri] = License(self._model, uri, self.id)
        return self._licenses[uri]

    def by_code(self, license_code, jurisdiction=None, version=None):
        # HACK: publicdomain is special
        if self.id == 'publicdomain':
            uri = 'http://creativecommons.org/licenses/publicdomain/'
        else:
            uri = cc.license.lib.dict2uri(dict(jurisdiction=jurisdiction,
                                               version=version,
                                               code=license_code))
        return self.by_uri(uri)

    def by_answers(self, answers_dict):
        raise NotImplementedError

    def questions(self):
        raise NotImplementedError

