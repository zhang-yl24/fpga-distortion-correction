"""Validate against analytic Gaussian transfer functions, without hardware."""
from pathlib import Path
import sys,json,hashlib,subprocess
import numpy as np
from scipy.special import erf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from slanted_edge_analysis import measure

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/project'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    test=subprocess.run([sys.executable,str(ROOT/'tests/test_slanted_edge_analysis.py')],capture_output=True,text=True)
    (OUT/'sfr-tests.log').write_text(test.stdout+test.stderr)
    if test.returncode or 'Ran 10 tests' not in test.stderr:raise ValueError('SFR regression failed')
    fig,axes=plt.subplots(1,2,figsize=(10,4),layout='constrained')
    y,x=np.mgrid[:128,:128];slope=np.tan(np.deg2rad(5))
    distance=(x-64-slope*(y-64)-.23)/np.sqrt(1+slope*slope)
    rows=[]
    for sigma,color in zip((1,1.5,2,3),('#006699','#9B4B00','#6E3B89','#256F46')):
        image=30+90*(1+erf(distance/(np.sqrt(2)*sigma)))
        r=measure(image);f=np.array(r['frequency_cycles_per_pixel']);truth=np.exp(-2*np.pi**2*sigma**2*f**2)
        expected=np.sqrt(np.log(2))/(np.sqrt(2)*np.pi*sigma)
        relative=abs(r['mtf50_cycles_per_pixel']-expected)/expected
        if relative>=.05:raise ValueError('Gaussian MTF50 accuracy exceeds 5 percent')
        rows.append({'sigma_px':sigma,'expected_mtf50_cycles_per_pixel':float(expected),
            'measured_mtf50_cycles_per_pixel':r['mtf50_cycles_per_pixel'],'relative_error':float(relative)})
        axes[0].plot(f,r['sfr'],color=color,label=f'sigma = {sigma:g} px')
        axes[0].plot(f,truth,color=color,linestyle='--',alpha=.6)
    axes[0].axhline(.5,color='black',linewidth=.8)
    axes[0].set(xlim=(0,.5),ylim=(0,1.05),xlabel='Frequency (cycles/pixel)',ylabel='Normalized SFR',title='Solid: estimator; dashed: analytic Gaussian')
    axes[0].legend()
    axes[1].plot([r['sigma_px'] for r in rows],[100*r['relative_error'] for r in rows],'o-',color='#006699')
    axes[1].axhline(5,color='black',linestyle='--',label='Test limit: 5%')
    axes[1].set(ylim=(0,6),xlabel='Gaussian sigma (pixels)',ylabel='MTF50 relative error (%)',title='Known synthetic blur only')
    axes[1].legend()
    fig.suptitle('Slanted-edge estimator validation — no optical camera acceptance',color='black')
    for ax in axes:
        ax.tick_params(colors='black');ax.xaxis.label.set_color('black');ax.yaxis.label.set_color('black')
    fig.savefig(OUT/'sfr-validation.png',dpi=170);plt.close(fig)
    files=('tools/slanted_edge_analysis.py','tools/validate-slanted-edge.py','tests/test_slanted_edge_analysis.py')
    result={'passed':True,'hardware_accessed':False,'optical_acceptance_complete':False,'host_tests':10,
        'analytic_cases':rows,'maximum_relative_error':max(r['relative_error'] for r in rows),
        'source_sha256':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest().upper() for n in files},
        'primary_method_sources':['https://www.imatest.com/imaging/sharpness/',
            'https://www.imatest.com/2015/04/lsf-correction-factor-for-slanted-edge-mtf-measurements/'],
        'limits':'Gaussian validation only. Not ISO-certified, not lens MTF, and not actual corrected-camera sharpness. Printed target, local scale and measured camera response must accompany physical results.'}
    (OUT/'sfr-validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':True,'tests':result['host_tests'],'maximum_relative_error':result['maximum_relative_error']}))

if __name__=='__main__':main()
