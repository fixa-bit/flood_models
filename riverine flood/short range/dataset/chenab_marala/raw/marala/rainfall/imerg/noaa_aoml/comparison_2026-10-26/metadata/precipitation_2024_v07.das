Attributes {
  time {
    String _CoordinateAxisType "Time";
    Float64 actual_range 1.7040672e+9, 1.7356878e+9;
    String axis "T";
    String calendar "julian";
    String ioos_category "Time";
    String long_name "Time";
    String origname "time";
    String standard_name "time";
    String time_origin "01-JAN-1970 00:00:00";
    String units "seconds since 1970-01-01T00:00:00Z";
  }
  latitude {
    String _CoordinateAxisType "Lat";
    Float32 actual_range -89.95, 89.95;
    String axis "Y";
    String ioos_category "Location";
    String long_name "Latitude";
    String standard_name "latitude";
    String units "degrees_north";
    Float32 valid_max 90.0;
    Float32 valid_min -90.0;
  }
  longitude {
    String _CoordinateAxisType "Lon";
    Float32 actual_range -179.95, 179.95;
    String axis "X";
    String ioos_category "Location";
    String long_name "Longitude";
    String standard_name "longitude";
    String units "degrees_east";
    Float32 valid_max 180.0;
    Float32 valid_min -180.0;
  }
  precipitation {
    UInt32 _ChunkSizes 1, 900, 1800;
    Float32 _FillValue 0.0;
    Float64 colorBarMaximum 15.0;
    Float64 colorBarMinimum 0.01;
    String colorBarPalette "Spectrum";
    String ioos_category "Meteorology";
    Float64 least_significant_digit 4;
    String long_name "Precipitation";
    Float32 missing_value 0.0;
    String origname "precipitation";
    String units "MM/Hr";
  }
  NC_GLOBAL {
    String cdm_data_type "Grid";
    String Conventions "COARDS, CF-1.10, ACDD-1.3";
    String DODS_EXTRA_Unlimited_Dimension "time";
    Float64 Easternmost_Easting 179.95;
    String FileHeader "DOI=10.5067/GPM/IMERG/3B-HH/07;
DOIauthority=https://dx.doi.org/;
DOIshortName=3IMERGHH;
AlgorithmID=3IMERGHH;
AlgorithmVersion=3IMERGH_7.0;
FileName=3B-HHR.MS.MRG.3IMERG.20241130-S233000-E235959.1410.V07B.HDF5;
SatelliteName=MULTI;
InstrumentName=MERGED;
GenerationDateTime=2025-03-30T23:39:47.000Z;
StartGranuleDateTime=2024-11-30T23:30:00.000Z;
StopGranuleDateTime=2024-11-30T23:59:59.999Z;
GranuleNumber=;
NumberOfSwaths=0;
NumberOfGrids=1;
GranuleStart=;
TimeInterval=HALF_HOUR;
ProcessingSystem=PPS;
ProductVersion=V07B;
EmptyGranule=NOT_EMPTY;
MissingData=;";
    String FileInfo "DataFormatVersion=7e;
TKCodeBuildVersion=0;
MetadataVersion=7e;
FormatPackage=HDF5-1.10.9;
BlueprintFilename=GPM.V7.3IMERGHH.blueprint.xml;
BlueprintVersion=BV_69;
TKIOVersion=3.101;
MetadataStyle=PVL;
EndianType=LITTLE_ENDIAN;";
    String fullnamepath "/Grid";
    Float64 geospatial_lat_max 89.95;
    Float64 geospatial_lat_min -89.95;
    Float64 geospatial_lat_resolution 0.1;
    String geospatial_lat_units "degrees_north";
    Float64 geospatial_lon_max 179.95;
    Float64 geospatial_lon_min -179.95;
    Float64 geospatial_lon_resolution 0.09999999999999999;
    String geospatial_lon_units "degrees_east";
    String GridHeader "BinMethod=ARITHMETIC_MEAN;
Registration=CENTER;
LatitudeResolution=0.1;
LongitudeResolution=0.1;
NorthBoundingCoordinate=90;
SouthBoundingCoordinate=-90;
EastBoundingCoordinate=180;
WestBoundingCoordinate=-180;
Origin=SOUTHWEST;";
    String history "2025-04-17 19:56:57 GMT hyrax-1.17.1 https://gpm1.gesdisc.eosdis.nasa.gov/opendap/GPM_L3/GPM_3IMERGHH.07/2024/335/3B-HHR.MS.MRG.3IMERG.20241130-S233000-E235959.1410.V07B.HDF5.nc4?precipitationQualityIndex,lat_bnds,precipitation,probabilityLiquidPrecipitation,randomError,time_bnds,lon_bnds,time,lon,lat,latv,nv,lonv%0D
2026-10-26T10:10:54Z (local files)
2026-10-26T10:10:54Z https://erddap.aoml.noaa.gov/hdb/erddap/griddap/precipitation_2024_v07.das";
    String infoUrl "???";
    String institution "???";
    String keywords "data, latitude, local, longitude, meteorology, precipitation, rain, rainfall, source, time";
    String license "The data may be used and redistributed for free but is not intended
for legal use, since it may contain inaccuracies. Neither the data
Contributor, ERD, NOAA, nor the United States Government, nor any
of their employees or contractors, makes any warranty, express or
implied, including warranties of merchantability and fitness for a
particular purpose, or assumes any legal liability for the accuracy,
completeness, or usefulness, of this information.";
    Float64 Northernmost_Northing 89.95;
    String sourceUrl "(local files)";
    Float64 Southernmost_Northing -89.95;
    String standard_name_vocabulary "CF Standard Name Table v70";
    String summary "Data from a local source.";
    String time_coverage_end "2024-12-31T23:30:00Z";
    String time_coverage_start "2024-01-01T00:00:00Z";
    String title "GPM IMERG Final Precipitation L3 Half Hourly 0.1 degree x 0.1 degree V07 2024";
    Float64 Westernmost_Easting -179.95;
  }
}
