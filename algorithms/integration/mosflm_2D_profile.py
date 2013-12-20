from __future__ import division
from dials.model.data import Reflection, ReflectionList
from dials.algorithms.integration import add_2d, subtrac_bkg_2d, fitting_2d
from scitbx.array_family import flex

def make_2d_profile(reflections):
  #print "len(reflections) =", len(reflections)
  big_nrow = 0
  big_ncol = 0
  max_i_01 = 0.0
  for ref in reflections:
    if ref.is_valid():
      if ref.intensity > max_i_01:
        max_i_01 = ref.intensity
  #print "max_i_01 =", max_i_01
  max_i = 0.0
  for ref in reflections:
    if ref.is_valid():
      if ref.intensity > max_i and ref.intensity < max_i_01 * 0.95:
        max_i = ref.intensity
  thold = 0.5 * max_i

  select_rlist = ReflectionList()
  for ref in reflections:
    if ref.is_valid() and ref.intensity > thold and ref.intensity < max_i:
      select_rlist.append(ref)
  counter = 0
  #print "len(select_rlist) =", len(select_rlist)
  for ref in select_rlist:
    local_nrow = ref.shoebox.all()[1]
    local_ncol = ref.shoebox.all()[2]
    if local_nrow > big_nrow:
      big_nrow = local_nrow
    if local_ncol > big_ncol:
      big_ncol = local_ncol
    counter += 1
  #print big_nrow, big_ncol
  big_nrow = big_nrow * 2 + 1
  big_ncol = big_ncol * 2 + 1
  sumation = flex.double(flex.grid(big_nrow, big_ncol))
  descr = flex.double(flex.grid(1, 3))
  for ref in select_rlist:
    shoebox = ref.shoebox
    #mask = ref.shoebox_mask                                 # may be needed soon
    background = ref.shoebox_background
    data2d = shoebox[0:1, :, :]
    #mask2d = mask[0:1, :, :]                                # may be needed soon
    background2d = background[0:1, :, :]
    data2d.reshape(flex.grid(shoebox.all()[1:]))
    #mask2d.reshape(flex.grid(shoebox.all()[1:]))            # may be needed soon
    background2d.reshape(flex.grid(shoebox.all()[1:]))

    descr[0, 0] = ref.centroid_position[0] - ref.bounding_box[0]
    descr[0, 1] = ref.centroid_position[1] - ref.bounding_box[2]
    descr[0, 2] = 1.0 / (ref.intensity * counter)
    peak2d = subtrac_bkg_2d(data2d, background2d)
    sumation = add_2d(descr, peak2d, sumation)

  return sumation, thold

def fit_profile_2d(reflections, arr_proff, row, col):
  average = arr_proff[row][col][0]
  thold = arr_proff[row][col][1]

  if_you_want_to_see_how_the_profiles_look = '''
  from matplotlib import pyplot as plt
  data2d = average.as_numpy_array()
  plt.imshow(data2d, interpolation = "nearest", cmap = plt.gray())
  plt.show()
  '''
  descr = flex.double(flex.grid(1, 3))
  for ref in reflections:
    if ref.is_valid() and ref.intensity < thold:
      shoebox = ref.shoebox
      #mask = ref.shoebox_mask                               # may be needed soon
      background = ref.shoebox_background
      ref.intensity = 0.0
      ref.intensity_variance = 0.0
      for i in range(shoebox.all()[0]):
        data2d = shoebox[i:i + 1, :, :]
        #mask2d = mask[i:i + 1, :, :]                        # may be needed soon
        background2d = background[i:i + 1, :, :]
        try:
          data2d.reshape(flex.grid(shoebox.all()[1:]))
          #mask2d.reshape(flex.grid(shoebox.all()[1:]))      # may be needed soon
          background2d.reshape(flex.grid(shoebox.all()[1:]))

        except:
          print "error reshaping flex-array"
          print "ref.bounding_box", ref.bounding_box
          break

        descr[0, 0] = ref.centroid_position[0] - ref.bounding_box[0]
        descr[0, 1] = ref.centroid_position[1] - ref.bounding_box[2]
        descr[0, 2] = 1.0 #/ (ref.intensity * counter)

        I_R = fitting_2d(descr, data2d, background2d, average)
        ref.intensity += I_R[0]
        ref.intensity_variance += I_R[1]

  return reflections
