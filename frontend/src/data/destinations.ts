/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { CampusDestination } from '../types.ts';

/**
 * Every campus building people might be headed to (about 300), searchable by name,
 * class-schedule code (WLH, PCYNH, CENTR) and other names (Ledden Auditorium, Calit2).
 *
 * Sources (verified 2026-10-21):
 * - Names, points, alias codes: UCSD campus GIS, "Building Points Public" layer, active
 *   buildings grouped so multi-part sites (Building A to F, additions) appear once.
 *   Utility, storage, laundry, lab-module and childcare buildings were left out.
 *   https://admin-enterprise-gis.ucsd.edu/server/rest/services/BaseData/Campus_Map_Vector/MapServer/26
 * - Class-schedule codes for the 24 general-assignment classroom buildings:
 *   https://facilities.ucsd.edu/Classrooms/
 *
 * `popular` is a display order for the "Popular" list shown before typing (lecture
 * halls, libraries, Price Center, RIMAC). It is our pick, not UCSD data; the backend's
 * GET /destinations can replace it with real search counts later.
 */
export const CAMPUS_DESTINATIONS: CampusDestination[] = [
  { id: "8980-villa-la-jolla-drive", name: "8980 Villa La Jolla Drive", aliases: ["La Jolla Innovation Center"], latitude: 32.87129, longitude: -117.23442 },
  { id: "africa-hall", name: "Africa Hall", aliases: ["ERC Africa Hall"], latitude: 32.88614, longitude: -117.24347 },
  { id: "alianza", name: "Alianza", latitude: 32.88316, longitude: -117.23922 },
  { id: "altman-clinical-translational-research-institute", name: "Altman Clinical Translational Research Institute", codes: ["ACTRI", "CTRI"], latitude: 32.87888, longitude: -117.22729 },
  { id: "amanecer", name: "Amanecer", aliases: ["North Campus Housing Phase I #3"], latitude: 32.88739, longitude: -117.24268 },
  { id: "anne-ratner-children-s-eye-center", name: "Anne Ratner Children's Eye Center", aliases: ["Ratner"], latitude: 32.87925, longitude: -117.2233 },
  { id: "applied-physics-and-mathematics", name: "Applied Physics and Mathematics", codes: ["APM"], aliases: ["AP&M"], popular: 15, latitude: 32.87901, longitude: -117.24135 },
  { id: "arena", name: "Arena", aliases: ["Mesa Nueva - Arena"], latitude: 32.8746, longitude: -117.22405 },
  { id: "argo-hall", name: "Argo Hall", aliases: ["Revelle Residence Hall - Argo"], latitude: 32.87438, longitude: -117.24159 },
  { id: "artesa", name: "Artesa", aliases: ["Mesa Nueva - Artesa"], latitude: 32.87477, longitude: -117.2222 },
  { id: "asante-house-east", name: "Asante House East", aliases: ["Asante E"], latitude: 32.8843, longitude: -117.24179 },
  { id: "asante-house-west", name: "Asante House West", aliases: ["Asante W"], latitude: 32.88432, longitude: -117.24211 },
  { id: "asia-hall", name: "Asia Hall", aliases: ["ERC Asia Hall"], latitude: 32.88579, longitude: -117.24347 },
  { id: "astilla", name: "Astilla", aliases: ["Nuevo East - Astilla"], latitude: 32.87469, longitude: -117.2207 },
  { id: "atkinson-hall", name: "Atkinson Hall", aliases: ["Calit2"], latitude: 32.8825, longitude: -117.23473 },
  { id: "atlantis-hall", name: "Atlantis Hall", aliases: ["Revelle Residence Hall Atlantis"], latitude: 32.87388, longitude: -117.24241 },
  { id: "audrey-geisel-university-house", name: "Audrey Geisel University House", aliases: ["Geisel House"], latitude: 32.87946, longitude: -117.24874 },
  { id: "azad", name: "Azad", aliases: ["TDLL Building 2"], latitude: 32.87244, longitude: -117.24307 },
  { id: "bates-hall", name: "Bates Hall", aliases: ["Single Graduate Apartments"], latitude: 32.88393, longitude: -117.23213 },
  { id: "beagle-hall", name: "Beagle Hall", aliases: ["Revelle Residence Hall Beagle"], latitude: 32.87409, longitude: -117.24263 },
  { id: "biology-building", name: "Biology Building", codes: ["M2B"], aliases: ["Muir Biology Building"], latitude: 32.87845, longitude: -117.24103 },
  { id: "biomedical-sciences-building", name: "Biomedical Sciences Building", codes: ["BSB"], aliases: ["Basic Sciences Building"], latitude: 32.87565, longitude: -117.23616 },
  { id: "birch-aquarium-at-scripps", name: "Birch Aquarium at Scripps", aliases: ["Birch"], latitude: 32.86584, longitude: -117.25067 },
  { id: "black-apartments", name: "Black Apartments", aliases: ["Warren Apartments - Black"], latitude: 32.88173, longitude: -117.23271 },
  { id: "blackhorse", name: "Blackhorse", latitude: 32.88104, longitude: -117.24397 },
  { id: "blake-hall", name: "Blake Hall", aliases: ["Revelle Residence Hall Blake"], latitude: 32.87483, longitude: -117.24159 },
  { id: "bonner-hall", name: "Bonner Hall", latitude: 32.87612, longitude: -117.24038 },
  { id: "borrego", name: "Borrego", aliases: ["North Campus Housing Phase II #2"], latitude: 32.88843, longitude: -117.24141 },
  { id: "brennan-apartments", name: "Brennan Apartments", aliases: ["Warren Apartments - Brennan"], latitude: 32.88278, longitude: -117.23286 },
  { id: "brian-c-malk-hall", name: "Brian C. Malk Hall", codes: ["MALK"], aliases: ["Malk Hall"], popular: 23, latitude: 32.88311, longitude: -117.24033 },
  { id: "brisa", name: "Brisa", latitude: 32.8743, longitude: -117.2247 },
  { id: "brown-hall", name: "Brown Hall", aliases: ["Single Graduate Apartments, Brown"], latitude: 32.88346, longitude: -117.23225 },
  { id: "cala", name: "Cala", aliases: ["Mesa Nueva - Cala"], latitude: 32.87565, longitude: -117.22218 },
  { id: "campus-emergency-services-building", name: "Campus Emergency Services Building", aliases: ["Emergency Services Building"], latitude: 32.88231, longitude: -117.22962 },
  { id: "canyon-vista", name: "Canyon Vista", aliases: ["Canyon Vista Administration Building"], latitude: 32.88398, longitude: -117.23323 },
  { id: "canyonview-aquatic-and-climbing-wall-facility", name: "Canyonview Aquatic and Climbing Wall Facility", aliases: ["Canyonview"], latitude: 32.8806, longitude: -117.23184 },
  { id: "canyonview-rec-athletics-administration", name: "Canyonview Rec/Athletics Administration", aliases: ["Canyonview Administration"], latitude: 32.88047, longitude: -117.23255 },
  { id: "capa", name: "Capa", latitude: 32.87522, longitude: -117.22012 },
  { id: "career-services-center", name: "Career Services Center", aliases: ["Career Services"], latitude: 32.87838, longitude: -117.23792 },
  { id: "catalyst", name: "Catalyst", codes: ["CTL"], aliases: ["NTPLL - Catalyst"], popular: 19, latitude: 32.88071, longitude: -117.24162 },
  { id: "cellular-and-molecular-medicine-east", name: "Cellular and Molecular Medicine East", codes: ["CMME"], aliases: ["CMM East"], latitude: 32.87637, longitude: -117.23769 },
  { id: "center-for-coastal-studies", name: "Center for Coastal Studies", codes: ["CCS"], aliases: ["CCS Building"], latitude: 32.86634, longitude: -117.25397 },
  { id: "center-for-memory-and-recording-research", name: "Center for Memory and Recording Research", codes: ["CMRR"], aliases: ["CMRR Building"], latitude: 32.88049, longitude: -117.23545 },
  { id: "center-for-neural-circuits-and-behavior", name: "Center for Neural Circuits and Behavior", codes: ["CNCB"], aliases: ["Center for Molecular Genetics"], latitude: 32.87553, longitude: -117.23837 },
  { id: "center-for-novel-therapeutics", name: "Center for Novel Therapeutics", codes: ["CNT"], aliases: ["Novel Therapeutics, Center for"], latitude: 32.87724, longitude: -117.22094 },
  { id: "center-for-translational-imaging-and-precision-medicine", name: "Center for Translational Imaging and Precision Medicine", aliases: ["Translational Imaging and Precision Med"], latitude: 32.87904, longitude: -117.22041 },
  { id: "center-hall", name: "Center Hall", codes: ["CENTR"], popular: 5, latitude: 32.878, longitude: -117.23718 },
  { id: "central-campus-trolley-station", name: "Central Campus Trolley Station", latitude: 32.87882, longitude: -117.232 },
  { id: "central-research-services", name: "Central Research Services", codes: ["CRS", "CRSF"], aliases: ["Cage Wash"], latitude: 32.87339, longitude: -117.2362 },
  { id: "challenger-hall", name: "Challenger Hall", aliases: ["Revelle Residence Hall Challenger"], latitude: 32.87416, longitude: -117.24233 },
  { id: "chaparral", name: "Chaparral", aliases: ["North Campus Housing Phase II #6"], latitude: 32.88759, longitude: -117.24204 },
  { id: "charles-david-keeling-apartments-1", name: "Charles David Keeling Apartments 1", aliases: ["Keeling 1"], latitude: 32.87425, longitude: -117.24304 },
  { id: "charles-david-keeling-apartments-2", name: "Charles David Keeling Apartments 2", aliases: ["Keeling 2"], latitude: 32.87361, longitude: -117.24323 },
  { id: "charles-david-keeling-apartments-3", name: "Charles David Keeling Apartments 3", aliases: ["Keeling 3"], latitude: 32.87363, longitude: -117.24284 },
  { id: "che-cafe", name: "Che Cafe", latitude: 32.87287, longitude: -117.23935 },
  { id: "clinical-research-facility", name: "Clinical Research Facility", codes: ["CRF"], latitude: 32.87454, longitude: -117.23417 },
  { id: "coalition", name: "Coalition", codes: ["COA"], popular: 22, latitude: 32.8821, longitude: -117.23993 },
  { id: "cognitive-science-building", name: "Cognitive Science Building", codes: ["CSB"], aliases: ["Cognitive Science"], popular: 16, latitude: 32.88048, longitude: -117.2396 },
  { id: "communication-building", name: "Communication Building", aliases: ["Communication"], latitude: 32.88148, longitude: -117.24024 },
  { id: "computer-science-and-engineering-building", name: "Computer Science and Engineering Building", codes: ["CSE", "EBU3B"], aliases: ["CSE Building", "CSE"], popular: 30, latitude: 32.88187, longitude: -117.23348 },
  { id: "conrad-prebys-music-center", name: "Conrad Prebys Music Center", codes: ["CPMC"], aliases: ["Prebys Music Center"], latitude: 32.87803, longitude: -117.23466 },
  { id: "copley-international-conference-center", name: "Copley International Conference Center", codes: ["CICC"], aliases: ["Copley International Conf Cent"], popular: 25, latitude: 32.88501, longitude: -117.24134 },
  { id: "coral", name: "Coral", aliases: ["North Campus Housing Phase I #8"], latitude: 32.88869, longitude: -117.2428 },
  { id: "cresta", name: "Cresta", aliases: ["Mesa Nueva - Cresta"], latitude: 32.87503, longitude: -117.22275 },
  { id: "cuzco-house-east", name: "Cuzco House East", aliases: ["ERC Cuzco House East"], latitude: 32.88464, longitude: -117.24185 },
  { id: "cuzco-house-west", name: "Cuzco House West", aliases: ["ERC Cuzco House West"], latitude: 32.88464, longitude: -117.24215 },
  { id: "design-and-innovation-building", name: "Design and Innovation Building", codes: ["SME2"], aliases: ["Engineering 2, Structural Materials and"], latitude: 32.87938, longitude: -117.23229 },
  { id: "discovery-hall", name: "Discovery Hall", aliases: ["Revelle Residence Hall Discovery"], latitude: 32.87409, longitude: -117.24184 },
  { id: "douglas-apartments", name: "Douglas Apartments", aliases: ["Douglas (Warren Apartments)"], latitude: 32.88328, longitude: -117.2332 },
  { id: "earth-hall", name: "Earth Hall", aliases: ["Earth Hall, Middle"], latitude: 32.88528, longitude: -117.24286 },
  { id: "east-campus-office-building", name: "East Campus Office Building", codes: ["ECOB"], latitude: 32.87643, longitude: -117.22739 },
  { id: "eckart-building", name: "Eckart Building", aliases: ["Carl H. Eckart Building"], latitude: 32.86722, longitude: -117.25252 },
  { id: "electromagnetics-research-facility", name: "Electromagnetics Research Facility", codes: ["ERF"], latitude: 32.86832, longitude: -117.24971 },
  { id: "engineering-building-unit-ii", name: "Engineering Building Unit II", codes: ["EBU2"], aliases: ["EBU-2"], latitude: 32.88116, longitude: -117.23302 },
  { id: "epstein-family-amphitheater", name: "Epstein Family Amphitheater", aliases: ["Epstein Amphitheater"], latitude: 32.87893, longitude: -117.23326 },
  { id: "erc-administration-north", name: "ERC Administration North", aliases: ["Administration North"], latitude: 32.88622, longitude: -117.24217 },
  { id: "erc-administration-south", name: "ERC Administration South", aliases: ["Administration South"], latitude: 32.88611, longitude: -117.24201 },
  { id: "estancia-la-jolla", name: "Estancia La Jolla", latitude: 32.88423, longitude: -117.24454 },
  { id: "europe-hall", name: "Europe Hall", aliases: ["ERC Europe Hall"], latitude: 32.88545, longitude: -117.24347 },
  { id: "eventide", name: "Eventide", aliases: ["North Campus Housing Phase I #5"], latitude: 32.88755, longitude: -117.24327 },
  { id: "exchange", name: "Exchange", aliases: ["Nuevo East - Exchange"], latitude: 32.87454, longitude: -117.21862 },
  { id: "extended-studies-and-public-programs", name: "Extended Studies and Public Programs", latitude: 32.88153, longitude: -117.24337 },
  { id: "extended-studies-and-public-programs-building-c", name: "Extended Studies and Public Programs - Building C", aliases: ["ESPP - Bldg C Addition"], latitude: 32.88183, longitude: -117.24306 },
  { id: "faculty-club", name: "Faculty Club", latitude: 32.87957, longitude: -117.23958 },
  { id: "foodworx", name: "Foodworx", aliases: ["Dining, Sixth College"], latitude: 32.87879, longitude: -117.2304 },
  { id: "foodworx-dining-room", name: "Foodworx Dining Room", latitude: 32.879, longitude: -117.23045 },
  { id: "frankfurter-hall", name: "Frankfurter Hall", aliases: ["Warren Residence Hall, Frankfurter"], latitude: 32.88435, longitude: -117.2328 },
  { id: "franklin-antonio-hall", name: "Franklin Antonio Hall", codes: ["FAH"], aliases: ["Engineering Building, Interdisciplinary"], popular: 14, latitude: 32.8835, longitude: -117.23482 },
  { id: "fred-n-spiess-hall", name: "Fred N. Spiess Hall", aliases: ["Spiess Hall"], latitude: 32.86907, longitude: -117.25098 },
  { id: "galathea-hall", name: "Galathea Hall", aliases: ["Revelle Residence Hall Galathea"], latitude: 32.87388, longitude: -117.24162 },
  { id: "galbraith-hall", name: "Galbraith Hall", codes: ["GH"], aliases: ["Library - Galbraith"], popular: 9, latitude: 32.87383, longitude: -117.24092 },
  { id: "geisel-library", name: "Geisel Library", aliases: ["Library - Geisel", "Library"], popular: 1, latitude: 32.88117, longitude: -117.23758 },
  { id: "geneva-hall-east", name: "Geneva Hall East", aliases: ["ERC Geneva Hall East"], latitude: 32.88559, longitude: -117.2419 },
  { id: "geneva-hall-west", name: "Geneva Hall West", aliases: ["ERC Geneva Hall West"], latitude: 32.88558, longitude: -117.24217 },
  { id: "george-palade-laboratories-for-cellular-and-molecular-medicine", name: "George Palade Laboratories for Cellular and Molecular Medicine", codes: ["GPL", "CMMW"], aliases: ["Cellular and Molecular Medicine West"], latitude: 32.87643, longitude: -117.23838 },
  { id: "gildred-latin-american-studies-building", name: "Gildred Latin American Studies Building", aliases: ["Gildred Lat Amer Studies"], latitude: 32.88557, longitude: -117.24134 },
  { id: "goldberg-apartments", name: "Goldberg Apartments", aliases: ["Warren Apartments - Goldberg"], latitude: 32.88275, longitude: -117.23376 },
  { id: "grassroots", name: "Grassroots", aliases: ["Apartments, Marshall G"], latitude: 32.88341, longitude: -117.24084 },
  { id: "great-hall", name: "Great Hall", aliases: ["ERC Great Hall"], latitude: 32.88392, longitude: -117.24191 },
  { id: "halicioglu-data-science-institute", name: "Halicioglu Data Science Institute", codes: ["HDSI"], aliases: ["Instruction and Research Facility 3000"], latitude: 32.88056, longitude: -117.23381 },
  { id: "hamilton-glaucoma-and-jacobs-retina-center", name: "Hamilton Glaucoma and Jacobs Retina Center", aliases: ["Glaucoma and Retina"], latitude: 32.87907, longitude: -117.22295 },
  { id: "harbor", name: "Harbor", aliases: ["North Campus Housing Phase I #2"], latitude: 32.88802, longitude: -117.24253 },
  { id: "harlan-hall", name: "Harlan Hall", aliases: ["Warren Residence Hall, Harlan"], latitude: 32.88476, longitude: -117.23251 },
  { id: "high-bay-physics-laboratory", name: "High Bay Physics Laboratory", aliases: ["High Bay"], latitude: 32.87969, longitude: -117.23429 },
  { id: "hubbs-hall", name: "Hubbs Hall", aliases: ["Marine Biology Building"], latitude: 32.86743, longitude: -117.2534 },
  { id: "human-rights", name: "Human Rights", aliases: ["Apartments, Marshall H"], latitude: 32.88317, longitude: -117.24101 },
  { id: "humanities-and-social-sciences", name: "Humanities and Social Sciences", codes: ["HSS", "LEDDN"], aliases: ["Ledden Auditorium"], popular: 11, latitude: 32.87851, longitude: -117.24167 },
  { id: "hyperion", name: "Hyperion", aliases: ["North Campus Housing Phase II #1"], latitude: 32.88864, longitude: -117.24149 },
  { id: "ida-and-cecil-green-faculty-club", name: "Ida and Cecil Green Faculty Club", aliases: ["Faculty Club"], latitude: 32.87919, longitude: -117.23952 },
  { id: "igpp-munk-laboratory", name: "IGPP - Munk Laboratory", aliases: ["Munk Laboratory"], latitude: 32.86831, longitude: -117.25302 },
  { id: "igpp-1000-revelle-laboratory", name: "IGPP 1000 - Revelle Laboratory", aliases: ["IGPP 1000"], latitude: 32.86844, longitude: -117.25242 },
  { id: "igpp-2000-revelle-laboratory", name: "IGPP 2000 - Revelle Laboratory", aliases: ["IGPP 2000"], latitude: 32.86781, longitude: -117.25245 },
  { id: "igpp-3000-revelle-laboratory", name: "IGPP 3000 - Revelle Laboratory", aliases: ["IGPP 3000"], latitude: 32.86782, longitude: -117.25224 },
  { id: "igpp-4000-revelle-laboratory", name: "IGPP 4000 - Revelle Laboratory", aliases: ["IGPP 4000"], latitude: 32.86837, longitude: -117.25216 },
  { id: "information-center-north-point-entrance", name: "Information Center - North Point Entrance", aliases: ["Information Center"], latitude: 32.88868, longitude: -117.24069 },
  { id: "institute-of-the-americas", name: "Institute of the Americas", aliases: ["IOA Addition"], latitude: 32.88505, longitude: -117.24096 },
  { id: "institute-of-the-americas-building", name: "Institute of the Americas Building", aliases: ["Institute of the Americas"], latitude: 32.88531, longitude: -117.24099 },
  { id: "isaacs-hall", name: "Isaacs Hall", codes: ["NORPAX"], latitude: 32.86968, longitude: -117.2523 },
  { id: "israni-biomedical-research-facility", name: "Israni Biomedical Research Facility", aliases: ["Israni BRF"], latitude: 32.87428, longitude: -117.23504 },
  { id: "j-craig-venter-institute", name: "J. Craig Venter Institute", codes: ["JCVI"], aliases: ["Venter Institute, J. Craig"], latitude: 32.86898, longitude: -117.24329 },
  { id: "jacobs-hall", name: "Jacobs Hall", codes: ["EBU1"], aliases: ["EBU-1"], latitude: 32.88166, longitude: -117.23528 },
  { id: "jacobs-medical-center-bed-tower", name: "Jacobs Medical Center - Bed Tower", codes: ["JMC"], aliases: ["Jacobs Medical Center Bed Tower"], popular: 31, latitude: 32.87775, longitude: -117.22639 },
  { id: "james-place", name: "James' Place", aliases: ["Black Box Restaurant"], latitude: 32.87188, longitude: -117.24087 },
  { id: "joan-and-irwin-jacobs-center-for-la-jolla-playhouse", name: "Joan and Irwin Jacobs Center for La Jolla Playhouse", aliases: ["Jacobs Center"], latitude: 32.87136, longitude: -117.2408 },
  { id: "justice", name: "Justice", aliases: ["Apartments, Marshall J"], latitude: 32.88281, longitude: -117.24113 },
  { id: "kaleidoscope", name: "Kaleidoscope", aliases: ["NTPLL - Kaleidoscope"], latitude: 32.88072, longitude: -117.243 },
  { id: "kathmandu-house-east", name: "Kathmandu House East", aliases: ["ERC Kathmandu House East"], latitude: 32.88498, longitude: -117.24189 },
  { id: "kathmandu-house-west", name: "Kathmandu House West", aliases: ["ERC Kathmandu House West"], latitude: 32.88498, longitude: -117.24217 },
  { id: "keck-oceanographic-and-atmospheric-research-1", name: "Keck Oceanographic and Atmospheric Research - 1", aliases: ["Keck OAR 1"], latitude: 32.8697, longitude: -117.25062 },
  { id: "keck-oceanographic-and-atmospheric-research-2", name: "Keck Oceanographic and Atmospheric Research - 2", aliases: ["Keck OAR 2"], latitude: 32.86941, longitude: -117.25045 },
  { id: "keck-oceanographic-and-atmospheric-research-3", name: "Keck Oceanographic and Atmospheric Research - 3", aliases: ["Keck OAR 3"], latitude: 32.86939, longitude: -117.25077 },
  { id: "kelp", name: "Kelp", aliases: ["North Campus Housing Phase I #6"], latitude: 32.88802, longitude: -117.24312 },
  { id: "knowledge", name: "Knowledge", aliases: ["Apartments, Marshall K"], latitude: 32.88298, longitude: -117.24181 },
  { id: "koman-family-outpatient-pavilion", name: "Koman Family Outpatient Pavilion", codes: ["KOP"], aliases: ["Koman OPP"], latitude: 32.87824, longitude: -117.22404 },
  { id: "la-jolla-health-trolley-station", name: "La Jolla Health Trolley Station", latitude: 32.88206, longitude: -117.2241 },
  { id: "la-jolla-institute-for-immunology", name: "La Jolla Institute for Immunology", codes: ["LJIAI"], aliases: ["Immunology, La Jolla Institute for"], latitude: 32.87718, longitude: -117.21963 },
  { id: "latin-america-hall", name: "Latin America Hall", aliases: ["ERC Latin America Hall"], latitude: 32.8851, longitude: -117.24347 },
  { id: "leichtag-family-foundation-biomedical-research-building", name: "Leichtag Family Foundation Biomedical Research Building", aliases: ["Leichtag"], latitude: 32.87665, longitude: -117.23686 },
  { id: "liberation", name: "Liberation", aliases: ["Apartments, Marshall L"], latitude: 32.88335, longitude: -117.24199 },
  { id: "main-gymnasium", name: "Main Gymnasium", aliases: ["Gymnasium, Main", "Main Gym"], popular: 27, latitude: 32.87715, longitude: -117.24124 },
  { id: "mandell-weiss-forum", name: "Mandell Weiss Forum", aliases: ["Forum Theater"], latitude: 32.87215, longitude: -117.24103 },
  { id: "mandell-weiss-theatre", name: "Mandell Weiss Theatre", aliases: ["Weiss Theatre, Mandell"], latitude: 32.87102, longitude: -117.24128 },
  { id: "mandeville-center", name: "Mandeville Center", codes: ["MANDE"], aliases: ["University Art Gallery"], popular: 12, latitude: 32.87779, longitude: -117.23997 },
  { id: "mandler-hall", name: "Mandler Hall", codes: ["MNDLR"], aliases: ["McGill Annex"], latitude: 32.8793, longitude: -117.24213 },
  { id: "marea", name: "Marea", aliases: ["Mesa Nueva - Marea"], latitude: 32.87453, longitude: -117.22323 },
  { id: "marine-conservation-and-technology-facility", name: "Marine Conservation and Technology Facility", codes: ["MCTF"], aliases: ["Marine Conservation and Technology"], latitude: 32.871, longitude: -117.25213 },
  { id: "marine-ecosystem-sensing-observation-and-modeling", name: "Marine Ecosystem Sensing Observation and Modeling", codes: ["MESOM"], latitude: 32.87004, longitude: -117.252 },
  { id: "marketplace", name: "Marketplace", aliases: ["Nuevo West - Marketplace"], latitude: 32.87539, longitude: -117.22455 },
  { id: "martin-johnson-house", name: "Martin Johnson House", aliases: ["Johnson Conference House"], latitude: 32.86909, longitude: -117.25293 },
  { id: "matthews-apartments-a", name: "Matthews Apartments A", latitude: 32.87896, longitude: -117.23136 },
  { id: "matthews-apartments-b", name: "Matthews Apartments B", latitude: 32.87871, longitude: -117.23083 },
  { id: "matthews-apartments-c", name: "Matthews Apartments C", latitude: 32.87851, longitude: -117.22997 },
  { id: "matthews-apartments-d", name: "Matthews Apartments D", latitude: 32.8783, longitude: -117.23067 },
  { id: "matthews-apartments-e", name: "Matthews Apartments E", latitude: 32.8783, longitude: -117.23116 },
  { id: "mayer-hall", name: "Mayer Hall", latitude: 32.87534, longitude: -117.24024 },
  { id: "mcgill-hall", name: "McGill Hall", codes: ["MCGIL"], popular: 18, latitude: 32.87901, longitude: -117.24205 },
  { id: "medical-teaching-facility", name: "Medical Teaching Facility", codes: ["MTF"], aliases: ["Teaching Facility, Medical"], latitude: 32.87594, longitude: -117.23543 },
  { id: "mesa-verde-hall-north", name: "Mesa Verde Hall North", aliases: ["ERC Mesa Verde Hall North"], latitude: 32.8861, longitude: -117.24145 },
  { id: "mesa-verde-hall-south", name: "Mesa Verde Hall South", aliases: ["ERC Mesa Verde Hall South"], latitude: 32.88585, longitude: -117.24145 },
  { id: "meteor-hall", name: "Meteor Hall", aliases: ["Revelle Residence Hall Meteor"], latitude: 32.87381, longitude: -117.24192 },
  { id: "middle-east-hall", name: "Middle East Hall", aliases: ["ERC Middle East Hall"], latitude: 32.88565, longitude: -117.24258 },
  { id: "molli-and-arthur-wagner-dance-building", name: "Molli and Arthur Wagner Dance Building", codes: ["DANCE"], aliases: ["Wagner Dance Building"], latitude: 32.87181, longitude: -117.24005 },
  { id: "moores-cancer-center", name: "Moores Cancer Center", aliases: ["Cancer Center"], latitude: 32.87829, longitude: -117.22287 },
  { id: "mosaic", name: "Mosaic", codes: ["MOS"], aliases: ["NTPLL - Mosaic"], popular: 20, latitude: 32.87994, longitude: -117.24187 },
  { id: "movement", name: "Movement", aliases: ["Apartments, Marshall M"], latitude: 32.88348, longitude: -117.24158 },
  { id: "narrative", name: "Narrative", aliases: ["Marshall Residence Hall - N"], latitude: 32.88351, longitude: -117.24253 },
  { id: "natatorium", name: "Natatorium", latitude: 32.87715, longitude: -117.2418 },
  { id: "natural-sciences-building", name: "Natural Sciences Building", codes: ["NSB"], aliases: ["Natural Sciences"], latitude: 32.87517, longitude: -117.24275 },
  { id: "new-scripps-administration", name: "New Scripps Administration", latitude: 32.86492, longitude: -117.25417 },
  { id: "nierenberg-hall", name: "Nierenberg Hall", latitude: 32.86848, longitude: -117.2512 },
  { id: "noaa-southwest-fisheries-science-center", name: "NOAA Southwest Fisheries Science Center", aliases: ["Southwest Fisheries Science Center, NOAA"], latitude: 32.87035, longitude: -117.25086 },
  { id: "north-america-hall", name: "North America Hall", aliases: ["ERC North America Hall"], latitude: 32.88475, longitude: -117.24348 },
  { id: "north-star", name: "North Star", aliases: ["North Campus Housing Phase I #1"], latitude: 32.88859, longitude: -117.24224 },
  { id: "ocean-drilling-program-core-building", name: "Ocean Drilling Program Core Building", aliases: ["ODP Core Building"], latitude: 32.86707, longitude: -117.25113 },
  { id: "oceania-hall", name: "Oceania Hall", aliases: ["ERC Oceania Hall"], latitude: 32.8849, longitude: -117.24256 },
  { id: "oceanview-terrace", name: "OceanView Terrace", aliases: ["OceanView"], latitude: 32.88314, longitude: -117.24269 },
  { id: "old-scripps", name: "Old Scripps", latitude: 32.86504, longitude: -117.25409 },
  { id: "one-miramar-street-1", name: "One Miramar Street - 1", latitude: 32.87353, longitude: -117.22631 },
  { id: "one-miramar-street-2", name: "One Miramar Street - 2", latitude: 32.87312, longitude: -117.22744 },
  { id: "one-miramar-street-3", name: "One Miramar Street - 3", latitude: 32.87385, longitude: -117.22674 },
  { id: "one-miramar-street-4", name: "One Miramar Street - 4", latitude: 32.87418, longitude: -117.22647 },
  { id: "one-miramar-street-5", name: "One Miramar Street - 5", latitude: 32.87387, longitude: -117.22582 },
  { id: "opportunity", name: "Opportunity", aliases: ["Marshall Residence Hall O"], latitude: 32.88353, longitude: -117.24269 },
  { id: "otterson-hall", name: "Otterson Hall", aliases: ["Management 1, Rady School of"], latitude: 32.88657, longitude: -117.24124 },
  { id: "outback-adventures", name: "Outback Adventures", latitude: 32.88923, longitude: -117.24036 },
  { id: "pacific-hall", name: "Pacific Hall", latitude: 32.87595, longitude: -117.24212 },
  { id: "peace", name: "Peace", aliases: ["Marshall Residence Hall - P"], latitude: 32.88353, longitude: -117.2429 },
  { id: "pepper-canyon-apartments", name: "Pepper Canyon Apartments", aliases: ["Pepper Canyon Apt 100"], latitude: 32.87899, longitude: -117.22949 },
  { id: "pepper-canyon-apartments-lodge", name: "Pepper Canyon Apartments Lodge", aliases: ["Pepper Canyon Lodge"], latitude: 32.87778, longitude: -117.23013 },
  { id: "pepper-canyon-hall", name: "Pepper Canyon Hall", codes: ["PCYNH", "PCH"], aliases: ["Multipurpose Building, Main Campus"], popular: 7, latitude: 32.87835, longitude: -117.23374 },
  { id: "perlman-ambulatory-care-unit", name: "Perlman Ambulatory Care Unit", aliases: ["Ambulatory Care Center - Thornton"], latitude: 32.87813, longitude: -117.22472 },
  { id: "peterson-hall", name: "Peterson Hall", codes: ["PETER"], aliases: ["Robert O. Peterson Hall"], popular: 6, latitude: 32.87997, longitude: -117.24022 },
  { id: "piedra", name: "Piedra", latitude: 32.87548, longitude: -117.22085 },
  { id: "plankton", name: "Plankton", aliases: ["North Campus Housing Phase I #7"], latitude: 32.88813, longitude: -117.24285 },
  { id: "podemos", name: "Podemos", codes: ["PODEM"], aliases: ["TDLL Building 5"], popular: 21, latitude: 32.87323, longitude: -117.24173 },
  { id: "porton", name: "Porton", latitude: 32.875, longitude: -117.21904 },
  { id: "powell-focht-bioengineering-hall", name: "Powell-Focht Bioengineering Hall", latitude: 32.88162, longitude: -117.23436 },
  { id: "preuss-school", name: "Preuss School", aliases: ["Preuss A"], latitude: 32.88284, longitude: -117.22166 },
  { id: "price-center-east", name: "Price Center East", aliases: ["Price East", "Price Center", "PC"], popular: 3, latitude: 32.87978, longitude: -117.23597 },
  { id: "price-center-west", name: "Price Center West", codes: ["PRICE"], aliases: ["Price West", "Price Center", "PC"], popular: 2, latitude: 32.87941, longitude: -117.23684 },
  { id: "pulse", name: "Pulse", aliases: ["TDLLN Building 1"], latitude: 32.87295, longitude: -117.24266 },
  { id: "quest", name: "Quest", aliases: ["Marshall Residence Hall Q"], latitude: 32.88353, longitude: -117.24315 },
  { id: "quino", name: "Quino", aliases: ["North Campus Housing Phase II #3"], latitude: 32.88823, longitude: -117.24165 },
  { id: "radiation-oncology-pet-ct-center", name: "Radiation Oncology PET/CT Center", aliases: ["PET/CT Center, Radiation Oncology"], latitude: 32.879, longitude: -117.22086 },
  { id: "recreation-gymnasium", name: "Recreation Gymnasium", aliases: ["Gymnasium, Recreational"], latitude: 32.87672, longitude: -117.24128 },
  { id: "residential-retail-and-supply-chain-services", name: "Residential, Retail and Supply Chain Services", latitude: 32.87453, longitude: -117.24302 },
  { id: "revolutionary", name: "Revolutionary", aliases: ["Marshall Residence Hall - R"], latitude: 32.88348, longitude: -117.24336 },
  { id: "ridge-walk-academic-building", name: "Ridge Walk Academic Building", codes: ["RWAC"], aliases: ["NTPLL - Ridge Walk"], popular: 13, latitude: 32.88042, longitude: -117.24095 },
  { id: "rimac", name: "RIMAC", codes: ["RIMAC"], aliases: ["LionTree Arena", "Recreation"], popular: 26, latitude: 32.88525, longitude: -117.23948 },
  { id: "rita-atkinson-residences", name: "Rita Atkinson Residences", aliases: ["Atkinson Residences"], latitude: 32.87253, longitude: -117.23519 },
  { id: "ritter-hall", name: "Ritter Hall", aliases: ["Ritter"], latitude: 32.86528, longitude: -117.25356 },
  { id: "robert-paine-scripps-forum-for-science-society-and-the-environment-auditorium", name: "Robert Paine Scripps Forum for Science Society and the Environment - Auditorium", aliases: ["Auditorium"], latitude: 32.86446, longitude: -117.25409 },
  { id: "robinson-building", name: "Robinson Building", codes: ["RBC"], aliases: ["Rady School of Management", "Robinson Building", "Rady"], popular: 24, latitude: 32.8846, longitude: -117.2411 },
  { id: "roger-revelle-student-center", name: "Roger Revelle Student Center", aliases: ["Revelle"], latitude: 32.86397, longitude: -117.25432 },
  { id: "rya", name: "Rya", aliases: ["North Tower"], latitude: 32.87805, longitude: -117.23267 },
  { id: "sally-t-wongavery-library", name: "Sally T. WongAvery Library", aliases: ["WongAvery Library", "Biomedical Library", "BLB"], popular: 29, latitude: 32.8751, longitude: -117.23695 },
  { id: "san-diego-supercomputer-center", name: "San Diego Supercomputer Center", codes: ["SDSC"], aliases: ["SDSC Central"], latitude: 32.88429, longitude: -117.23999 },
  { id: "sanford-consortium-for-regenerative-medicine", name: "Sanford Consortium for Regenerative Medicine", codes: ["SANF"], aliases: ["Sanford"], latitude: 32.88951, longitude: -117.24405 },
  { id: "sankofa", name: "Sankofa", aliases: ["TDLL Building 4"], latitude: 32.87254, longitude: -117.242 },
  { id: "scholander-hall", name: "Scholander Hall", aliases: ["Scholander"], latitude: 32.86592, longitude: -117.25373 },
  { id: "school-of-medicine", name: "School of Medicine", latitude: 32.87504, longitude: -117.23415 },
  { id: "science-and-engineering-research-facility", name: "Science and Engineering Research Facility", codes: ["SERF"], latitude: 32.87961, longitude: -117.23503 },
  { id: "scripps-pier-laboratory", name: "Scripps Pier Laboratory", aliases: ["Pier Laboratory, Scripps"], latitude: 32.86694, longitude: -117.2571 },
  { id: "shiley-eye", name: "Shiley Eye", aliases: ["Shiley Expansion"], latitude: 32.87946, longitude: -117.22267 },
  { id: "shiley-eye-institute", name: "Shiley Eye Institute", aliases: ["Shiley"], latitude: 32.87947, longitude: -117.22302 },
  { id: "skaggs-pharmaceutical-sciences-building", name: "Skaggs Pharmaceutical Sciences Building", codes: ["PSB"], aliases: ["Pharmaceutical"], latitude: 32.87422, longitude: -117.23571 },
  { id: "social-sciences-building", name: "Social Sciences Building", codes: ["SSB"], popular: 17, latitude: 32.88404, longitude: -117.24046 },
  { id: "social-sciences-research-building", name: "Social Sciences Research Building", codes: ["SSRB"], aliases: ["CRB (SSRB)"], latitude: 32.88062, longitude: -117.2401 },
  { id: "solidarity", name: "Solidarity", aliases: ["Marshall Residence Hall S"], latitude: 32.88345, longitude: -117.24352 },
  { id: "solis-hall", name: "Solis Hall", codes: ["SOLIS"], popular: 10, latitude: 32.88094, longitude: -117.23964 },
  { id: "solstice", name: "Solstice", aliases: ["North Campus Housing Phase I #4"], latitude: 32.88747, longitude: -117.24306 },
  { id: "south-entrance-visitor-information", name: "South Entrance Visitor Information", latitude: 32.87346, longitude: -117.23765 },
  { id: "spanos-athletic-performance-center", name: "Spanos Athletic Performance Center", latitude: 32.89033, longitude: -117.24047 },
  { id: "spanos-athletic-training-facility", name: "Spanos Athletic Training Facility", aliases: ["Spanos"], latitude: 32.88979, longitude: -117.24043 },
  { id: "splash-cafe-at-birch-aquarium", name: "Splash Cafe at Birch Aquarium", aliases: ["Splash"], latitude: 32.86578, longitude: -117.25007 },
  { id: "stein-clinical-research-building", name: "Stein Clinical Research Building", codes: ["SCR"], aliases: ["Stein"], latitude: 32.87603, longitude: -117.234 },
  { id: "stewart-commons", name: "Stewart Commons", aliases: ["Roots and Pines"], latitude: 32.87891, longitude: -117.24254 },
  { id: "stewart-hall", name: "Stewart Hall", aliases: ["Warren Residence Hall, Stewart"], latitude: 32.88423, longitude: -117.23232 },
  { id: "structural-and-materials-engineering-building", name: "Structural and Materials Engineering Building", codes: ["SME"], latitude: 32.87982, longitude: -117.23303 },
  { id: "student-center-a", name: "Student Center A", latitude: 32.87738, longitude: -117.24036 },
  { id: "student-center-b", name: "Student Center B", latitude: 32.87724, longitude: -117.23881 },
  { id: "student-center-pub", name: "Student Center Pub", aliases: ["Porter's Pub and Stage"], latitude: 32.87704, longitude: -117.23947 },
  { id: "student-services-center", name: "Student Services Center", codes: ["SSC"], aliases: ["Services Center, Student"], popular: 28, latitude: 32.87856, longitude: -117.23552 },
  { id: "sulpizio-family-cardiovascular-center", name: "Sulpizio Family Cardiovascular Center", codes: ["CVC"], aliases: ["Cardiovascular Center, Sulpizio Family"], latitude: 32.8787, longitude: -117.22611 },
  { id: "sumner-auditorium", name: "Sumner Auditorium", aliases: ["Sumner"], latitude: 32.86488, longitude: -117.25292 },
  { id: "survivance", name: "Survivance", aliases: ["TDLL Building 3"], latitude: 32.87195, longitude: -117.24277 },
  { id: "sverdrup-hall", name: "Sverdrup Hall", aliases: ["Sverdrup"], latitude: 32.86442, longitude: -117.25317 },
  { id: "t-denny-sanford-medical-education-and-telemedicine-center", name: "T. Denny Sanford Medical Education and Telemedicine Center", codes: ["MET"], aliases: ["Medical Education and Telemedicine"], latitude: 32.87532, longitude: -117.23474 },
  { id: "tamarack-apartments-east", name: "Tamarack Apartments East", aliases: ["Tamarack East"], latitude: 32.8783, longitude: -117.24229 },
  { id: "tamarack-apartments-west", name: "Tamarack Apartments West", aliases: ["Tamarack West"], latitude: 32.87825, longitude: -117.24254 },
  { id: "tapestry", name: "Tapestry", aliases: ["NTPLL - Tapestry"], latitude: 32.87996, longitude: -117.243 },
  { id: "tata-hall", name: "Tata Hall", aliases: ["Biological and Physical Sciences"], latitude: 32.8764, longitude: -117.24155 },
  { id: "tenaya-hall", name: "Tenaya Hall", aliases: ["Muir Residence Hall - Tenaya"], latitude: 32.87941, longitude: -117.243 },
  { id: "the-forum", name: "The Forum", aliases: ["Gallery/Multi-Purpose"], latitude: 32.87801, longitude: -117.23533 },
  { id: "the-jeannie", name: "The Jeannie", aliases: ["Jeannie P. Rivkin Auditorium"], latitude: 32.87991, longitude: -117.24122 },
  { id: "the-strand", name: "The Strand", latitude: 32.88791, longitude: -117.24203 },
  { id: "thomas-wayland-vaughan-hall", name: "Thomas Wayland Vaughan Hall", aliases: ["Vaughan"], latitude: 32.86527, longitude: -117.25297 },
  { id: "thornmint", name: "Thornmint", aliases: ["North Campus Housing Phase II #4"], latitude: 32.88784, longitude: -117.24164 },
  { id: "thornton-pavilion", name: "Thornton Pavilion", aliases: ["John M. and Sally B. Thornton Pavilion"], latitude: 32.87802, longitude: -117.22563 },
  { id: "tierra", name: "Tierra", latitude: 32.8748, longitude: -117.2212 },
  { id: "tioga-hall", name: "Tioga Hall", aliases: ["Muir Residence Hall - Tioga"], latitude: 32.87904, longitude: -117.24336 },
  { id: "torrey-pines-center-north", name: "Torrey Pines Center North", codes: ["TPCN"], aliases: ["Aerojet Headquarters Building"], latitude: 32.89116, longitude: -117.24255 },
  { id: "torrey-pines-center-south", name: "Torrey Pines Center South", codes: ["TPCS"], latitude: 32.89031, longitude: -117.24319 },
  { id: "triton-administrative-services-building", name: "Triton Administrative Services Building", latitude: 32.87745, longitude: -117.23613 },
  { id: "triton-alumni-and-welcome-center", name: "Triton Alumni and Welcome Center", latitude: 32.87815, longitude: -117.23614 },
  { id: "triton-clubhouse", name: "Triton Clubhouse", latitude: 32.8813, longitude: -117.22548 },
  { id: "triton-health-and-wellness-building", name: "Triton Health and Wellness Building", latitude: 32.87777, longitude: -117.23643 },
  { id: "triton-stadium", name: "Triton Stadium", latitude: 32.8809, longitude: -117.2264 },
  { id: "truth", name: "Truth", aliases: ["Marshall Residence Hall T"], latitude: 32.88302, longitude: -117.24352 },
  { id: "tuolumne-apartments-s-house-east", name: "Tuolumne Apartments - S House East", aliases: ["S House East"], latitude: 32.87847, longitude: -117.24326 },
  { id: "tuolumne-apartments-s-house-north", name: "Tuolumne Apartments - S House North", aliases: ["S House North"], latitude: 32.87866, longitude: -117.24324 },
  { id: "tuolumne-apartments-s-house-south", name: "Tuolumne Apartments - S House South", aliases: ["S House South"], latitude: 32.87834, longitude: -117.2434 },
  { id: "tuolumne-apartments-s-house-west", name: "Tuolumne Apartments - S House West", aliases: ["S House West"], latitude: 32.87855, longitude: -117.24341 },
  { id: "tuolumne-apartments-t-house-east", name: "Tuolumne Apartments - T House East", aliases: ["T House East"], latitude: 32.87837, longitude: -117.24278 },
  { id: "tuolumne-apartments-t-house-north", name: "Tuolumne Apartments - T House North", aliases: ["T House North"], latitude: 32.87836, longitude: -117.24301 },
  { id: "tuolumne-apartments-t-house-south", name: "Tuolumne Apartments - T House South", aliases: ["T House South"], latitude: 32.87822, longitude: -117.2429 },
  { id: "tuolumne-apartments-t-house-west", name: "Tuolumne Apartments - T House West", aliases: ["T House West"], latitude: 32.87823, longitude: -117.24315 },
  { id: "umoja", name: "Umoja", latitude: 32.88248, longitude: -117.23935 },
  { id: "unity", name: "Unity", aliases: ["Marshall Residence Hall - U"], latitude: 32.883, longitude: -117.24335 },
  { id: "university-center", name: "University Center", latitude: 32.87904, longitude: -117.23474 },
  { id: "urey-hall", name: "Urey Hall", latitude: 32.87555, longitude: -117.24128 },
  { id: "vela", name: "Vela", aliases: ["Pepper Canyon Housing South"], latitude: 32.87713, longitude: -117.23272 },
  { id: "ventanas", name: "Ventanas", aliases: ["Cafe Ventanas"], latitude: 32.88615, longitude: -117.2428 },
  { id: "veterans-affairs-medical-center", name: "Veterans Affairs Medical Center", codes: ["VAMC"], aliases: ["VA Hospital"], latitude: 32.87552, longitude: -117.23229 },
  { id: "viento", name: "Viento", latitude: 32.87507, longitude: -117.2251 },
  { id: "vireo", name: "Vireo", aliases: ["North Campus Housing Phase II #5"], latitude: 32.88755, longitude: -117.24163 },
  { id: "visual-arts-facility", name: "Visual Arts Facility", latitude: 32.87941, longitude: -117.23421 },
  { id: "viterbi-family-vision-research-center", name: "Viterbi Family Vision Research Center", aliases: ["Viterbi"], latitude: 32.87931, longitude: -117.22395 },
  { id: "voice", name: "Voice", aliases: ["Marshall Residence Hall V"], latitude: 32.88295, longitude: -117.24313 },
  { id: "w-m-keck-building", name: "W. M. Keck Building", aliases: ["Keck fMRI"], latitude: 32.875, longitude: -117.23617 },
  { id: "warren-field-house", name: "Warren Field House", latitude: 32.8806, longitude: -117.2292 },
  { id: "warren-lecture-hall", name: "Warren Lecture Hall", codes: ["WLH"], popular: 4, latitude: 32.88057, longitude: -117.23435 },
  { id: "warren-student-activity-center", name: "Warren Student Activity Center", aliases: ["Courtroom, The"], latitude: 32.88242, longitude: -117.23328 },
  { id: "wells-fargo-hall", name: "Wells Fargo Hall", codes: ["WFH"], aliases: ["School of Management 2, Rady"], latitude: 32.88695, longitude: -117.24174 },
  { id: "york-hall", name: "York Hall", codes: ["YORK"], aliases: ["Undergraduate Sciences Building"], popular: 8, latitude: 32.87451, longitude: -117.24 },
];

/** Destination selected when the app first loads. */
export const DEFAULT_DESTINATION_ID = 'geisel-library';

/** O(1) lookup by ID, built once, instead of scanning the list on every render. */
export const DESTINATIONS_BY_ID: ReadonlyMap<string, CampusDestination> = new Map(
  CAMPUS_DESTINATIONS.map((d) => [d.id, d])
);

/** Popular places in display order, for the list shown before the user types. */
export const POPULAR_DESTINATIONS: CampusDestination[] = CAMPUS_DESTINATIONS.filter(
  (d) => d.popular !== undefined
).sort((a, b) => a.popular! - b.popular!);

/**
 * Dropped pins (tap the map) are stored as IDs like "pin:32.88012,-117.23711" so the
 * rest of the app (requests, "your usual") keeps passing plain string IDs.
 */
const PIN_PREFIX = 'pin:';

export function makePinDestinationId(latitude: number, longitude: number): string {
  return `${PIN_PREFIX}${latitude.toFixed(5)},${longitude.toFixed(5)}`;
}

function parsePinDestination(id: string): CampusDestination | null {
  if (!id.startsWith(PIN_PREFIX)) return null;
  const [lat, lng] = id.slice(PIN_PREFIX.length).split(',').map(Number);
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
  return { id, name: 'Dropped pin', latitude: lat, longitude: lng, isPin: true };
}

/** Looks up a building or dropped pin by ID; returns undefined if unknown. */
export function findDestination(id: string): CampusDestination | undefined {
  return DESTINATIONS_BY_ID.get(id) ?? parsePinDestination(id) ?? undefined;
}

/** Returns the destination for an ID, falling back to the default destination. */
export function getDestination(id: string): CampusDestination {
  return findDestination(id) ?? DESTINATIONS_BY_ID.get(DEFAULT_DESTINATION_ID)!;
}

/** Lowercase, and treat "&", "-" and "." as spaces so "AP&M" and "ap m" both match. */
function normalize(text: string): string {
  return text.toLowerCase().replace(/[&.\-/,()']/g, ' ').replace(/\s+/g, ' ').trim();
}

export interface DestinationMatch {
  destination: CampusDestination;
  /** What matched, when it was not the name itself (shown under the name). */
  matchedOn?: string;
}

/**
 * Ranks destinations for a search box. Exact schedule codes win ("wlh" puts Warren
 * Lecture Hall first), then names that start with the query, then any word in the
 * name, then other names. Popular places break ties.
 */
export function searchDestinations(query: string, limit = 30): DestinationMatch[] {
  const q = normalize(query);
  if (!q) return [];
  const qCompact = q.replace(/ /g, '');
  const scored: Array<{ score: number; match: DestinationMatch }> = [];

  for (const d of CAMPUS_DESTINATIONS) {
    let score = Infinity;
    let matchedOn: string | undefined;
    const name = normalize(d.name);

    for (const code of d.codes ?? []) {
      const c = code.toLowerCase();
      if (c === qCompact) { score = 0; matchedOn = code; break; }
      if (qCompact.length >= 2 && c.startsWith(qCompact) && score > 1) { score = 1; matchedOn = code; }
    }
    if (score > 2 && name.startsWith(q)) { score = 2; matchedOn = undefined; }
    if (score > 3 && (` ${name}`).includes(` ${q}`)) { score = 3; matchedOn = undefined; }
    if (score > 4 && name.includes(q)) { score = 4; matchedOn = undefined; }
    if (score > 5) {
      const alias = d.aliases?.find((a) => normalize(a).includes(q));
      if (alias) { score = 5; matchedOn = alias; }
    }
    if (score === Infinity) continue;
    // Popular places float up within the same tier
    const tieBreak = d.popular !== undefined ? d.popular / 1000 : 0.5;
    scored.push({ score: score + tieBreak, match: { destination: d, matchedOn } });
  }

  return scored
    .sort((a, b) => a.score - b.score || a.match.destination.name.localeCompare(b.match.destination.name))
    .slice(0, limit)
    .map((s) => s.match);
}
