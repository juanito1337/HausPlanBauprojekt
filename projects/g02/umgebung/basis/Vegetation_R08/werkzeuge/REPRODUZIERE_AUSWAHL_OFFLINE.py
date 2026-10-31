"""Recalculate R08 image/height selection from delivered GeoTIFF crops and ROIs.
Offline only; numpy, rasterio, scipy, shapely are required. Does not touch NX.
Default: compare with delivered masks; optional --out writes a NEW npz file.
This validates reproducibility, not classification or survey correctness.
"""
from pathlib import Path
import json,argparse
import numpy as np
import rasterio
from scipy.interpolate import RegularGridInterpolator
from scipy import ndimage
from shapely.geometry import Polygon
from shapely import contains_xy

def recalculate(base):
    rules=json.loads((base/'data/SEGMENTIERUNGSREGELN_R08.json').read_text(encoding='utf-8'))
    review=json.loads((base/'data/AUSWAHL_R08.json').read_text(encoding='utf-8'))
    job=json.loads((base/'data/BAUAUFTRAG_VEGETATION_R08.json').read_text(encoding='utf-8'))
    site=json.loads((base/'quellen/R06_KARTENBEZUG_UNVERAENDERT.json').read_text(encoding='utf-8'))
    R=np.array(job['transform']['basis_rows_local_xy_in_EN']);origin=np.array(job['transform']['origin_EN_m'])
    with rasterio.open(base/'data/DOP_RGBI_2025_AUSSCHNITT.tif') as ds:rgbi=ds.read();transform=ds.transform;shape=ds.shape
    with rasterio.open(base/'data/BDOM_2023_AUSSCHNITT.tif') as ds:
        if ds.transform!=transform or ds.shape!=shape:raise ValueError('Source rasters do not align')
        dom=ds.read(1)
    x=transform.c+transform.a*(np.arange(shape[1])+.5);y=transform.f+transform.e*(np.arange(shape[0])+.5);e,n=np.meshgrid(x,y)
    with rasterio.open(base/'data/DGM_R07_AUSSCHNITT.tif') as ds:
        arr=ds.read(1);tf=ds.transform;gx=tf.c+tf.a*(np.arange(ds.width)+.5);gy=tf.f+tf.e*(np.arange(ds.height)+.5)
        if gy[0]>gy[-1]:gy=gy[::-1];arr=arr[::-1]
        ground=RegularGridInterpolator((gy,gx),arr,bounds_error=True)(np.stack([n,e],axis=-1))
    h=dom-ground;ndvi=(rgbi[3].astype(float)-rgbi[0])/(rgbi[3].astype(float)+rgbi[0]+1e-6)
    boundary=Polygon(np.array(site['boundary']['points_local_mm'])/1000@R+origin)
    house=Polygon(np.array(site['cadastral_house']['points_local_mm'])/1000@R+origin)
    roofmask=contains_xy(house.buffer(rules['house_buffer_m']),e,n)
    offset=np.array(rules['offset_origin_utm_m'])
    for pp in rules['exclusion_polygons_offsets']:roofmask|=contains_xy(Polygon(np.array(pp)+offset),e,n)
    zone=contains_xy(boundary.buffer(rules['review_mask_buffer_m']),e,n);owned=contains_xy(boundary,e,n)
    labels=np.zeros(shape,np.int16);spectral_labels=np.zeros_like(labels)
    def keep_large(mask):
        ll,_=ndimage.label(mask,np.ones((3,3)));counts=np.bincount(ll.ravel());ids=np.flatnonzero(counts>=rules['min_component_nodes']);ids=ids[ids!=0]
        return np.isin(ll,ids)
    for k,rec in enumerate(review['regions'],1):
        roi=contains_xy(Polygon(rec['review_polygon_utm_m']),e,n)&zone&~roofmask
        spectral=(ndvi>=rules['spectral_threshold'])&roi
        candidate=spectral&(h>=rules['min_height_difference_m'])&np.isfinite(h)
        selected=keep_large(candidate)&(labels==0);spectral&=spectral_labels==0
        labels[selected]=k;spectral_labels[spectral]=k
    lowpoly=Polygon(np.array(rules['low_cover_roi_offsets'])+offset)
    low=contains_xy(lowpoly,e,n)&owned&~roofmask&(ndvi>=rules['spectral_threshold'])&(h<rules['low_max_height_difference_m'])&(h>=rules['low_min_height_difference_m'])
    low=keep_large(low)
    return {'labels':labels,'spectral_labels':spectral_labels,'low':low,'dom':dom,'ground':ground,'h':h,'ndvi':ndvi,'e':e,'n':n,'local':(np.stack([e,n],axis=-1)-origin)@R.T}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out');args=parser.parse_args();base=Path(__file__).absolute().parents[1]
    result=recalculate(base)
    with np.load(base/'data/RASTER_AUSWERTUNG_R08.npz',allow_pickle=False) as reference:
        for key in ['labels','spectral_labels','low']:np.testing.assert_array_equal(result[key],reference[key])
    if args.out:
        path=Path(args.out)
        if path.exists():raise FileExistsError(str(path))
        with path.open('xb') as file:np.savez_compressed(file,**result)
    print('R08 masks reproduced exactly from source crops and documented ROIs; no proof of present-day vegetation.')
