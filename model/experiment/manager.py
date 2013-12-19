class Experiment(object):

  __slots__ = ('imageset', 'beam', 'detector', 'goniometer', 'scan', 'crystal')

  def __init__(self, imageset=None, beam=None, detector=None,
               goniometer=None, scan=None, crystal=None):
    self.imageset = imageset
    self.beam = beam
    self.detector = detector
    self.goniometer = goniometer
    self.scan = scan
    self.crystal = crystal

  def __contains__(self, item):
    return (item is self.imageset or
            item is self.beam or
            item is self.detector or
            item is self.goniometer or
            item is self.scan or
            item is self.crystal)

  def __eq__(self, other):
    if not isinstance(other, Experiment):
      return False
    return (self.imageset is other.imageset and
            self.beam is other.beam and
            self.detector is other.detector and
            self.goniometer is other.goniometer and
            self.scan is other.scan and
            self.crystal is other.crystal)

  def __ne__(self, other):
    return not self.__eq__(other)


class ExperimentManager(object):

  def __init__(self, item=None):
    if item is not None:
      self._data = list(item)
    else:
      self._data = list()

  def __setitem__(self, index, item):
    if isinstance(item, Experiment):
      self._data[index] = item
    else:
      raise TypeError('expected type Experiment, got %s' % type(item))

  def __getitem__(self, index):
    if isinstance(index, slice):
      return ExperimentManager(self._data[index])
    return self._data[index]

  def __delitem__(self, index):
    del self._data[index]

  def __len__(self):
    return len(self._data)

  def __iter__(self):
    for e in self._data:
      yield e

  def __contains__(self, item):
    return item in self._data or any(item in e for e in self._data)

  def index(self, item):
    return self._data.index(item)

  def append(self, item):
    if isinstance(item, Experiment):
      self._data.append(item)
    else:
      raise TypeError('expected type Experiment, got %s' % type(item))

  def extend(self, other):
    if isinstance(other, ExperimentManager):
      self._data.extend(other._data)
    else:
      raise TypeError('expected type ExperimentManager, got %s' % type(item))

  def replace(self, a, b):
    for i in self.indices(a):
      exp = self._data[i]
      if   exp.imageset is a:   exp.imageset = b
      elif exp.beam is a:       exp.beam = b
      elif exp.detector is a:   exp.detector = b
      elif exp.goniometer is a: exp.goniometer = b
      elif exp.scan is a:       exp.scan = b
      elif exp.crystal is a:    exp.crystal = b
      else: raise ValueError('unidentified model %s' % a)

  def remove(self, model):
    self.replace(model, None)

  def indices(self, model):
    if isinstance(model, list) or isinstance(model, tuple):
      return list(set.intersection(*[set(self.indices(m)) for m in model]))
    else:
      return [i for i, e in enumerate(self) if model in e]

  def beams(self):
    return list(set([e.beam for e in self]))

  def detectors(self):
    return list(set([e.detector for e in self]))

  def goniometers(self):
    return list(set([e.goniometer for e in self]))

  def scans(self):
    return list(set([e.scan for e in self]))

  def crystals(self):
    return list(set([e.crystal for e in self]))

  def imagesets(self):
    return list(set([e.imageset for e in self]))


class ExperimentListDict(object):

  def __init__(self, obj):
    from copy import deepcopy
    self._obj = deepcopy(obj)

  def decode(self):

    # Extract lists of models referenced by experiments
    self._blist = self._extract_models('beam')
    self._dlist = self._extract_models('detector')
    self._glist = self._extract_models('goniometer')
    self._slist = self._extract_models('scan')
    self._clist = self._extract_models('crystal')

    # Go through all the imagesets and make sure the dictionary
    # references by an index rather than a file path. Experiments
    # referencing the same imageset will get different objects
    # due to the fact that we can have different models
    self._ilist = self._extract_imagesets()

    # Extract all the experiments
    return self._extract_experiments()

  def _extract_models(self, name):

    # The from dict function
    from_dict = getattr(self, '_%s_from_dict' % name)

    # Extract all the model list
    mlist = self._obj.get(name, [])

    # Convert the model from dictionary to concreate
    # python class for the model.
    mlist = [from_dict(d) for d in mlist]

    # Dictionaries for file mappings
    mmap = {}

    # For each experiment, check the model is not specified by
    # a path, if it is then get the dictionary of the model
    # and insert it into the list. Replace the path reference
    # with an index
    for eobj in self._obj['experiment']:
      value = eobj.get(name, None)
      if value is None:
        continue
      elif isinstance(value, str):
        if value not in mmap:
          mmap[value] = len(mlist)
          mlist.append(from_dict(ExperimentListDict._from_file(value)))
        eobj[name] = mmap[value]
      elif not isinstance(value, int):
        raise TypeError('expected int or str, got %s' % type(value))

    # Return the model list
    return mlist

  def _extract_imagesets(self):

    # Extract all the model list
    mlist = self._obj.get('imageset', [])

    # Dictionaries for file mappings
    mmap = {}

    # For each experiment, check the imageset is not specified by
    # a path, if it is then get the dictionary of the imageset
    # and insert it into the list. Replace the path reference
    # with an index
    for eobj in self._obj['experiment']:
      value = eobj.get('imageset', None)
      if value is None:
        continue
      elif isinstance(value, str):
        if value not in mmap:
          mmap[value] = len(mlist)
          mlist.append(ExperimentListDict._from_file(value))
        eobj['imageset'] = mmap[value]
      elif not isinstance(value, int):
        raise TypeError('expected int or str, got %s' % type(value))

    # Return the model list
    return mlist

  def _extract_experiments(self):
    from dials.model.experiment.manager import ExperimentManager

    # For every experiment, use the given input to create
    # a sensible experiment.
    el = ExperimentManager()
    for eobj in self._obj['experiment']:
      el.append(self._create_experiment(
        ExperimentListDict.model_or_none(self._ilist, eobj, 'imageset'),
        ExperimentListDict.model_or_none(self._blist, eobj, 'beam'),
        ExperimentListDict.model_or_none(self._dlist, eobj, 'detector'),
        ExperimentListDict.model_or_none(self._glist, eobj, 'goniometer'),
        ExperimentListDict.model_or_none(self._slist, eobj, 'scan'),
        ExperimentListDict.model_or_none(self._clist, eobj, 'crystal')))

    # Return the experiment list
    return el

  def _create_experiment(self, imageset, beam, detector, goniometer, scan,
                         crystal):

    # Create the imageset from the input data
    if imageset is None:
      imageset = self._make_null()
    elif imageset['__id__'] == 'ImageSet':
      imageset = self._make_stills(imageset)
    elif imageset['__id__'] == 'ImageSweep':
      imageset = self._make_sweep(imageset, scan)

    # Fill in any models if they aren't already there
    if beam is None:
      beam = imageset.get_beam()
    if detector is None:
      detector = imageset.get_detector()
    if goniometer is None:
      goniometer = imageset.get_goniometer()
    if scan is None:
      scan = imageset.get_scan()

    # Return the experiment instance
    return Experiment(
      imageset=imageset,
      beam=beam,
      detector=detector,
      goniometer=goniometer,
      scan=scan,
      crystal=crystal
    )

  def _make_null(self):
    raise RuntimeError('NullSet not yet supported')

  def _make_stills(self, imageset):
    from dxtbx.imageset2 import ImageSetFactory
    return ImageSetFactory.make_imageset(imageset['images'])

  def _make_sweep(self, imageset, scan):
    from os.path import abspath, expanduser, expandvars
    from dxtbx.sweep_filenames import template_image_range
    from dxtbx.format.Registry import Registry
    from dxtbx.imageset2 import ImageSetFactory

    # Get the template format
    template = abspath(expanduser(expandvars(imageset['template'])))
    pfx = template.split('#')[0]
    sfx = template.split('#')[-1]
    template_format = '%s%%0%dd%s' % (pfx, template.count('#'), sfx)

    # Get the number of images (if no scan is given we'll try
    # to find all the images matching the template
    if scan is None:
      i0, i1 = template_image_range(template)
    else:
      i0, i1 = scan.get_image_range()

    # Get the format class from the first image
    format_class = Registry.find(template_format % i0)

    # Make a sweep from the input data
    return ImageSetFactory.make_sweep(template,
      list(range(i0, i1+1)), format_class)

  @staticmethod
  def model_or_none(mlist, eobj, name):
    index = eobj.get(name, None)
    if index is not None:
      return mlist[index]
    return None

  @staticmethod
  def _beam_from_dict(obj):
    from dxtbx.model import Beam
    return Beam.from_dict(obj)

  @staticmethod
  def _detector_from_dict(obj):
    from dxtbx.model import Detector, HierarchicalDetector
    if 'hierarchy' in obj:
      return HierarchicalDetector.from_dict(obj)
    else:
      return Detector.from_dict(obj)

  @staticmethod
  def _goniometer_from_dict(obj):
    from dxtbx.model import Goniometer
    return Goniometer.from_dict(obj)

  @staticmethod
  def _scan_from_dict(obj):
    from dxtbx.model import Scan
    return Scan.from_dict(obj)

  @staticmethod
  def _crystal_from_dict(obj):
    from dials.model.serialize import crystal
    return crystal.crystal_from_dict(obj)

  @staticmethod
  def _from_file(filename):
    from dxtbx.serialize.load import _decode_dict
    from os.path import expanduser, expandvars, abspath
    import json
    filename = abspath(expanduser(expandvars(filename)))
    try:
      with open(filename, 'r') as infile:
        return json.loads(infile.read(), object_hook=_decode_dict)
    except IOError, e:
      raise IOError('unable to read file, %s' % filename)


class ExperimentManagerFactory(object):

  @staticmethod
  def from_datablock(datablock):
    pass

  @staticmethod
  def from_imageset_list_and_crystal(imageset_list, crystal):
    em = ExperimentManager()
    for imageset in imageset_list:
      em.extend(ExperimentManagerFactory.from_imageset(imageset, crystal))
    return em

  @staticmethod
  def from_imageset_and_crystal(imageset):
    pass

  @staticmethod
  def from_dict(obj):
    return ExperimentListDict(obj).decode()

  @staticmethod
  def from_json(text):
    from dxtbx.serialize.load import _decode_dict
    import json
    return ExperimentManagerFactory.from_dict(
      json.loads(text, object_hook=_decode_dict))

  @staticmethod
  def from_json_file(filename):
    with open(filename, 'r') as infile:
      return ExperimentManagerFactory.from_json(infile.read())




from dials.model.experiment import Beam, Detector, Goniometer, Scan, Crystal

if __name__ == '__main__':

  crystal0 = Crystal((1, 0, 0), (0, 1, 0), (0, 0, 1), 1)
  crystal1 = Crystal((1, 0, 0), (0, 1, 0), (0, 0, 1), 1)
  crystal2 = Crystal((1, 0, 0), (0, 1, 0), (0, 0, 1), 1)

  detector0 = Detector()
  detector1 = Detector()
  detector2 = detector0

  beam0 = Beam()
  beam1 = beam0
  beam2 = beam1

  expr0 = Experiment(beam=beam0, detector=detector0, crystal=crystal0)
  expr1 = Experiment(beam=beam1, detector=detector1, crystal=crystal1)
  expr2 = Experiment(beam=beam2, detector=detector2, crystal=crystal2)

  em = ExperimentManager()
  em.append(expr0)
  em.append(expr1)
  em.append(expr2)

  print "Unique Crystals"
  print em.crystals()

  print "Unique Beams"
  print em.beams()

  print "Unique Detectors"
  print em.detectors()

  print "Experiments with crystal:"
  print em.indices(crystal0)
  print em.indices(crystal1)
  print em.indices(crystal2)

  print "Experiments with beam:"
  print em.indices(beam0)
  print em.indices(beam1)
  print em.indices(beam2)

  print "Experiments with detector:"
  print em.indices(detector0)
  print em.indices(detector1)
  print em.indices(detector2)

  print "Experiments with detector/crystal combinations"
  print em.indices((detector0, crystal0))
  print em.indices((detector0, crystal1))
  print em.indices((detector0, crystal2))
  print em.indices((detector1, crystal0))
  print em.indices((detector1, crystal1))
  print em.indices((detector1, crystal2))
  print em.indices((detector2, crystal0))
  print em.indices((detector2, crystal1))
  print em.indices((detector2, crystal2))

  print "Replace model"
  em.replace(detector1, detector0)
  print em.detectors()

  print detector0 in em
  print detector1 in em

  em.extend(em)
  print em
