#darc, the Durham Adaptive optics Real-time Controller.
#Copyright (C) 2010 Alastair Basden.

#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU Affero General Public License as
#published by the Free Software Foundation, either version 3 of the
#License, or (at your option) any later version.

#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU Affero General Public License for more details.

#You should have received a copy of the GNU Affero General Public License
#along with this program.  If not, see <http://www.gnu.org/licenses/>.
import correlation,FITS
import tel
import numpy
nacts=52#97#54#+256
ncam=2#one camera with 128x256 and 1 camera with 128x128
ncamThreads=numpy.ones((ncam,),numpy.int32)*2
npxly=numpy.zeros((ncam,),numpy.int32)
npxly[:]=128
npxlx=npxly.copy()
npxlx[0]=256
nsuby=npxly.copy()
nsuby[:]=7
#nsuby[4:]=16
nsubx=nsuby.copy()
nsubx[0]=14
nsubapsTot=(nsuby*nsubx).sum()
subapFlag=numpy.zeros((nsubapsTot,),numpy.int32)
#subapFlag[:]=1
subapFlag[nsubapsTot/3*2:]=tel.Pupil(7*16,7*8,8,7).subflag.astype("i").ravel()
subapFlag[0:nsubapsTot/3*2:2]=subapFlag[nsubapsTot/3*2:]
subapFlag[1:nsubapsTot/3*2:2]=subapFlag[nsubapsTot/3*2:]
#subapFlag=tel.Pupil(7*16,7*8,8,7).subflag.astype("i").ravel()#numpy.ones((nsubaps,),"i")

#ncents=nsubaps*2
ncents=subapFlag.sum()*2
npxls=(npxly*npxlx).sum()

bgImage=None#FITS.Read("shimgb1stripped_bg.fits")[1].astype("f")#numpy.zeros((npxls,),"f")
darkNoise=None#FITS.Read("shimgb1stripped_dm.fits")[1].astype("f")
flatField=None#FITS.Read("shimgb1stripped_ff.fits")[1].astype("f")
#indx=0
#nx=npxlx/nsubx
#ny=npxly/nsuby
#correlationPSF=numpy.zeros((npxls,),numpy.float32)


subapLocation=numpy.zeros((nsubapsTot,6),"i")
nsubaps=nsuby*nsubx#cumulative subap
nsubapsCum=numpy.zeros((ncam+1,),numpy.int32)
ncentsCum=numpy.zeros((ncam+1,),numpy.int32)
for i in range(ncam):
    nsubapsCum[i+1]=nsubapsCum[i]+nsubaps[i]
    ncentsCum[i+1]=ncentsCum[i]+subapFlag[nsubapsCum[i]:nsubapsCum[i+1]].sum()*2
kalmanPhaseSize=nacts#assume single layer turbulence...
HinfT=numpy.random.random((ncents,kalmanPhaseSize*3)).astype("f")-0.5
kalmanHinfDM=numpy.random.random((kalmanPhaseSize*3,kalmanPhaseSize)).astype("f")-0.5
Atur=numpy.random.random((kalmanPhaseSize,kalmanPhaseSize)).astype("f")-0.5
invN=numpy.random.random((nacts,kalmanPhaseSize)).astype("f")

# now set up a default subap location array...
ystep=numpy.array([1,1])
xstep=numpy.array([2,1])
xin=8#number of pixels in from edge of image that first subap starts
yin=8
subx=(npxlx-2*xin*xstep)/nsubx*xstep
suby=(npxly-2*yin*ystep)/nsuby*ystep
for k in range(ncam):
    for i in range(nsuby[k]):
        for j in range(nsubx[k]):
            indx=nsubapsCum[k]+i*nsubx[k]+j
            if subapFlag[indx]:
                subapLocation[indx]=(yin*ystep[k]+i*suby[k],yin*ystep[k]+i*suby[k]+suby[k],ystep[k],xin*xstep[k]+j%xstep[k]+(j/xstep[k])*subx[k],xin*xstep[k]+j%xstep[k]+(j/xstep[k])*subx[k]+subx[k],xstep[k])

cameraParams=numpy.zeros((10,),numpy.int32)
cameraParams[0]=128*8#blocksize
cameraParams[1]=1000#timeout/ms
cameraParams[2]=0#port
cameraParams[3]=0xffff#thread affinity
cameraParams[4]=1#thread priority
cameraParams[5]=128*8#blocksize
cameraParams[6]=1000#timeout/ms
cameraParams[7]=1#port
cameraParams[8]=0xffff#thread affinity
cameraParams[9]=1#thread priority
centroiderParams=numpy.zeros((10,),numpy.int32)
centroiderParams[0]=18#blocksize
centroiderParams[1]=1000#timeout/ms
centroiderParams[2]=0#port
centroiderParams[3]=-1#thread affinity
centroiderParams[4]=1#thread priority
centroiderParams[5]=18#blocksize
centroiderParams[6]=1000#timeout/ms
centroiderParams[7]=1#port
centroiderParams[8]=-1#thread affinity
centroiderParams[9]=1#thread priority
rmx=numpy.zeros((ncents,nacts),'f')#FITS.Read("rmxRTC.fits")[1].transpose().astype("f")
#gainRmxT=rmx.transpose().copy()

mirrorParams=numpy.zeros((4,),"i")
mirrorParams[0]=1000#timeout/ms
mirrorParams[1]=2#port
mirrorParams[2]=-1#thread affinity
mirrorParams[3]=1#thread prioirty

#Now describe the DM - this is for the GUI only, not the RTC.
#The format is: ndms, N for each DM, actuator numbers...
#Where ndms is the number of DMs, N is the number of linear actuators for each, and the actuator numbers are then an array of size NxN with entries -1 for unused actuators, or the actuator number that will set this actuator in the DMC array.
dmDescription=numpy.zeros((8*8+1+1,),numpy.int16)
dmDescription[0]=1#1 DM
dmDescription[1]=8#1st DM has nacts linear actuators
tmp=dmDescription[2:]
tmp[:]=-1
tmp.shape=8,8
dmflag=tel.Pupil(8,4,0).fn.ravel()
numpy.put(tmp,dmflag.nonzero()[0],numpy.arange(52))


pxlcnt=numpy.zeros((nsubapsTot,),"i")

# set up the pxlCnt array - number of pixels to wait until each subap is ready.  Here assume identical for each camera.
for k in range(ncam):
    # tot=0#reset for each camera
    for i in range(nsuby[k]):
        for j in range(nsubx[k]):
            indx=nsubapsCum[k]+i*nsubx[k]+j
            n=(subapLocation[indx,1]-1)*npxlx[k]+subapLocation[indx,4]
            pxlcnt[indx]=n
#pxlcnt[-3:]=npxls#not necessary, but means the RTC reads in all of the pixels... so that the display shows whole image

control={
    "switchRequested":0,#this is the only item in a currently active buffer that can be changed...
    "pause":0,
    "go":1,
    #"DMgain":0.25,
    #"staticTerm":None,
    "maxClipped":nacts,
    "refCentroids":None,
    #"dmControlState":0,
    #"gainReconmxT":None,#numpy.random.random((ncents,nacts)).astype("f"),#reconstructor with each row i multiplied by gain[i].
    #"dmPause":0,
    #"reconMode":"closedLoop",
    #"applyPxlCalibration":0,
    "centroidMode":"CoG",#whether data is from cameras or from WPU.
    #"centroidAlgorithm":"wcog",
    "windowMode":"basic",
    #"windowMap":None,
    #"maxActuatorsSaturated":10,
    #"applyAntiWindup":0,
    #"tipTiltGain":0.5,
    #"laserStabilisationGain":0.1,
    "thresholdAlgorithm":0,
    #"acquireMode":"frame",#frame, pixel or subaps, depending on what we should wait for...
    "reconstructMode":"simple",#simple (matrix vector only), truth or open
    "centroidWeighting":None,
    "v0":numpy.zeros((nacts,),"f"),#v0 from the tomograhpcic algorithm in openloop (see spec)
    #"gainE":None,#numpy.random.random((nacts,nacts)).astype("f"),#E from the tomo algo in openloop (see spec) with each row i multiplied by 1-gain[i]
    #"clip":1,#use actMax instead
    "bleedGain":0.0,#0.05,#a gain for the piston bleed...
    "midRangeValue":32768,#midrange actuator value used in actuator bleed
    "actMax":65535,#4095,#max actuator value
    "actMin":0,#4095,#max actuator value
    #"gain":numpy.zeros((nacts,),numpy.float32),#the actual gains for each actuator...
    "nacts":nacts,
    "ncam":ncam,
    "nsuby":nsuby,
    "nsubx":nsubx,
    "npxly":npxly,
    "npxlx":npxlx,
    "ncamThreads":ncamThreads,
    #"pxlCnt":numpy.zeros((ncam,nsuby,nsubx),"i"),#array of number of pixels to wait for next subap to have arrived.
    "pxlCnt":pxlcnt,
    #"subapLocation":numpy.zeros((ncam,nsuby,nsubx,4),"i"),#array of ncam,nsuby,nsubx,4, holding ystart,yend,xstart,xend for each subap.
    "subapLocation":subapLocation,
    #"bgImage":numpy.zeros((ncam,npxly,npxlx),"f"),#an array, same size as image
    "bgImage":bgImage,
    "darkNoise":darkNoise,
    "closeLoop":1,
    #"flatField":numpy.ones((ncam,npxly,npxlx),"f"),#an array same size as image.
    "flatField":flatField,#numpy.random.random((npxls,)).astype("f"),
    "thresholdValue":0.,
    "powerFactor":1.,#raise pixel values to this power.
    "subapFlag":subapFlag,
    #"randomCCDImage":0,#whether to have a fake CCD image...
    "usingDMC":0,#whether using DMC
    "kalmanHinfT":HinfT,#Hinfinity, transposed...
    "kalmanHinfDM":kalmanHinfDM,
    "kalmanPhaseSize":kalmanPhaseSize,
    "kalmanAtur":Atur,
    "kalmanReset":0,
    "kalmanInvN":invN,
    "kalmanUsed":0,#whether to use Kalman...
    "fakeCCDImage":None,
    "printTime":0,#whether to print time/Hz
    "rmx":rmx,#numpy.random.random((nacts,ncents)).astype("f"),
    "gain":numpy.ones((nacts,),"f")*0.5,
    "E":numpy.zeros((nacts,nacts),"f"),#E from the tomoalgo in openloop.
    "threadAffinity":None,
    "threadPriority":None,
    "delay":0,
    "clearErrors":0,
    "camerasOpen":0,
    "camerasFraming":0,
    #"cameraParams":None,
    #"cameraName":"andorpci",
    "cameraName":"sl240Int32cam",#"camfile",
    "cameraParams":cameraParams,
    "mirrorName":"dmcSL240mirror",
    "mirrorParams":mirrorParams,
    "mirrorOpen":0,
    "frameno":0,
    "switchTime":numpy.zeros((1,),"d")[0],
    "adaptiveWinGain":0.5,
    "correlationThresholdType":0,
    "correlationThreshold":0.,
    "fftCorrelationPattern":None,#correlation.transformPSF(correlationPSF,ncam,npxlx,npxly,nsubx,nsuby,subapLocation),
#    "correlationPSF":correlationPSF,
    "nsubapsTogether":1,
    "nsteps":0,
    "addActuators":0,
    "actuators":None,#(numpy.random.random((3,52))*1000).astype("H"),#None,#an array of actuator values.
    "actSequence":None,#numpy.ones((3,),"i")*1000,
    "recordCents":0,
    "pxlWeight":None,
    "averageImg":0,
    "centroidersOpen":0,
    "centroidersFraming":0,
    "centroidersParams":centroiderParams,
    "centroidersName":"sl240centroider",
    "actuatorMask":None,
    "dmDescription":dmDescription,
    "averageCent":0,
    "centCalData":None,
    "centCalBounds":None,
    "centCalSteps":None,
    }

