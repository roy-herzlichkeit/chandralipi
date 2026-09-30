
Chandrayaan-2 TMC2 PDS4 Data Archive

Contents:
1. Introduction
2. Archive Contents
3. Contacts for more information


1.  INTRODUCTION
This is readme file containing details about the PDS4 Data Archive of TMC2 payload
of Chandrayaan-2 mission


2.  ARCHIVE CONTENTS

Under TMC2 instrument wise data collection, data is organized under each directory
defined by PDS4. Data is organized based on the levels of data processing and data
products definitions.

To handle requirement of archiving the data products for 12 orbits in a day, data
products are organized into year, month and day wise as yyyymmdd. The year month and 
day wise directory contains PDS4 data products including PDS4 Label products.

Below is detailed TMC2 data archive structure

tmc_collection
|--bundle.xml
|--readme.txt
|
|--browse
|  |
|  |--raw
|  |  |--yyyymmdd
|  |     |--data_product
|  |
|  |--calibrated
|  |  |--yyyymmdd
|  |     |-- data_product
|  |
|  |--derived
|  |  |--yyyymmdd
|  |     |-- data_product
|  |
|--data
|  |
|  |--raw
|  |  |--yyyymmdd
|  |     |-- data_product
|  |
|  |--calibrated
|  |  |--yyyymmdd
|  |     |-- data_product
|  |
|  |--derived
|  |  |--yyyymmdd
|  |     |-- data_product
|  |
|--geometry
|  |--calibrated
|  |  |--yyyymmdd
|  |     |-- data_product
|  |
|--miscellaneous
|  |
|  |--collection_miscellaneous_inventory.csv
|  |--collection_miscellaneous_inventory.xml
|  |
|  |--raw
|  |  |--yyyymmdd
|  |     |-- data_product
|  |
|  |--calibrated
|  |  |--yyyymmdd
|  |     |-- data_product
|  |
|--calibration
|  |--collection_calibration_inventory.csv
|  |--collection_calibration_inventory.xml
|  |--look up table files
|  |--look up table xml files
|  |
|--document
|  |--collection_document_inventory.csv
|  |--collection_document_inventory.xml
|  |--ch2_tmc2_pds_dp_archive_sis.pdf
|  |--ch2_tmc2_pds_dp_archive_sis.xml
|  |

The details about the data_product file naming conventions and formats 
please refer section 6.5 and 7 in data products archive software interface 
specification document (ch2_tmc2_pds_dp_archive_sis.pdf) under document 
collection.


2.1.  The observational data collections

Under the data directory there are three separate subdirectory based on the 
defined PDS4 data products levels raw, calibrated and derived. Under each 
sub directories, there are again sub directory based on year, month and day 
wise. The year, month and day wise subdirectory contains PDS4 data products 
mainly image for three sensors defined as Fore, Aft and Nadir and associated 
label files in XML format.

2.2.  The Calibration Collection

The calibration directory contains calibration files used to process the data 
products, or calibration data needed to use the data products. This calibration 
files are the look up table files that got generated during ground calibration 
exercise. All these lookup table files naming convention is based on the 
parameters mission (ch2), instrument (tmc), sensors (fore, aft and nadir), 
gain (g1), exposure (e1, e2, e3, e4), version (v1,v2...) and byte selection 
(msb, lsb and mid).

2.3.  The Document Collection

The document directory contains documentation to help the user understand and use 
the archive data. The document collection contains data products and archive software 
interface specification document data product contains end to end to description about 
the mission, payload, data products (content, format, file naming convention) and 
archive structure as per PDS4 standard. 

2.4.  The Browse Collection

Under the Browse directory there is a separate subdirectory which is year, month 
and day wise for each type of product. The year, month and day wise subdirectory 
contains browse image for each image, which is a down sampled version of the full 
resolution image, with the size of m pixels x n lines and 8 bits per pixel, is 
defined as an object and contained in the data file. PNG images derived from the 
browse image are stored in this directory, as well as the label files pointing to 
these images. All the browse PNG images are named as per file naming convention 
in section 6.5 of DP and Archive SIS document under document collection.


2.5.  The Geometry Collection

Under the geometry directory there are three separate subdirectory based on the 
defined PDS4 data products levels raw, calibrated and derived. Under each sub 
directories, there are again sub directory based on year, month and day wise. 
The year, month and day wise subdirectory contains PDS4 data products mainly 
grid file in csv format for three sensors defined as Fore, Aft and Nadir and 
associated label files in XML format. All the grid files are named as per 
file naming conventions in section 6.5 of DP and Archive SIS document under 
document collection.


2.6.  The Miscellaneous Collection

Under the miscellaneous directory there are two separate subdirectory based 
on the defined PDS4 data products levels raw and calibrated. Under each sub 
directories, there are again sub directory based on year, month and day wise. 
The year, month and day wise subdirectory contains data products mainly orbit 
and attitude file (oat), orbit and attitude header file (oath), liberation angle 
file (lbr) and sun parameter file (spm) in ASCII text format All the files with 
extension oat, oath, lbr and spm files are named as per file naming conventions 
in section 6.5 of DP and Archive SIS document under document collection. 
It also contains the supplementary information provided by data provider to be 
useful in the interpretation and use of other collections in the bundle but 
which does not fit within the scope of the other collections


3.  CONTACTS FOR MORE INFORMATION
=============================================================================
1. Dr. Ashutosh Arya
   Principal Investigator (PI)
   Space Applications Centre
   Ahmedabad
   Phone: 07926914107
   Email id: arya_as@sac.isro.gov.in

2. Amitabh
   Deputy Project Director (DPD) Data Products
   Space Applications Centre
   Ahmedabad
   Phone: 07926914727
   Email id: amitabh@sac.isro.gov.in

3. Ajay Kumar Prashar
   PDS4 Technical Support
   Space Applications Centre
   Ahmedabad
   Phone: 07926914764
   Email id: ajay_prashar@sac.isro.gov.in

4. Sreenath
   Operations Support Team
   ISTRAC
   Bengaluru
   Phone: 08028094416, 08022029173
   Email id: sreenath@istrac.gov.in
===========================================================================
