# Simple test program for sensor fusion on Pyboard
# Author Peter Hinch
# V0.7 25th June 2015 Adapted for new MPU9x50 interface

import pyb
from mpu9250 import MPU9250
from fusion import Fusion
from usched import Sched, Poller, wait
from nmeagenerator import HDG, CMP
#import compy
import LSM303
import pickle
i2c_object = None

class TiltCompensatedCompass:

    def __init__(self, imu, hmc_side=2):
        self.imu = imu
#        self.hml=compy.compass(hmc_side)
#        self.hml.setDeclination(0)
#        self.hml.setContinuousMode()
        self.hml=LSM303.TiltCompCompass(hmc_side)
        self.hml.setDeclination(0)
        self.hml.setContinuousMode()
        self.gyrobias=(-1.394046, 1.743511, 0.4735878)
        self.fuse = Fusion()
        self.fuse.magbias=(43.6694, -1.2140, 32.3375) #based on benchtest
        self.fuse.scalebias=(1,1,1)
        self.fuseh = Fusion()#TODO: temp for comparison
#        self.fuseh.magbias=(-19.397,-71.753,33.872)
        self.fuseh.magbias=(-4.8839,30.7156,5.1349)
        self.fuseh.scalebias=(1,1,1)#TODO: temp for comparison
        self.update()
        self.hrp = [self.fuse.heading, self.fuse.roll, self.fuse.pitch]

    def poll(self, dummy):
        self.update()
        if self.hrp[0] != self.fuse.heading:
            self.hrp = [self.fuse.heading, self.fuse.roll, self.fuse.pitch]
            return 1
        return None

    def update(self):
        accel = self.imu.accel.xyz
        gyroraw = self.imu.gyro.xyz

        gyro = [gyroraw[0] - self.gyrobias[0], gyroraw[1] - self.gyrobias[1], gyroraw[2] - self.gyrobias[2]]

        self.mag = self.imu.mag.xyz        #TODO: global for temp calibration
        self.magh = self.hml.getAxes()     #TODO: temp for comparison
        self.fuse.update(accel, gyro, self.mag)
        self.fuseh.update(accel, gyro, self.magh) #TODO: temp for comparison

    def getmag(self):
        return self.imu.mag.xyz

    def Calibrate(self):
        print("Calibrating. Press switch when done.")
        sw = pyb.Switch()
        self.fuse.calibrate(self.getmag, sw, lambda: pyb.delay(100))
        print(self.fuse.magbias)

    def gyrocal(self):
        xa=0
        ya=0
        za=0
        for x in range(0,100):
            xyz=self.imu.gyro.xyz
            xa+=xyz[0]
            ya+=xyz[1]
            za+=xyz[2]
            pyb.delay(1000)
        print(xa/100,ya/100,za/100)

    def view(self):
        while True:
            self.update()
            print("{0}    {1}".format(self.fuse.heading,self.fuseh.heading))

    @property
    def heading(self):
        return self.hrp[0]

    @property
    def roll(self):
        return self.hrp[1]

    @property
    def pitch(self):
        return self.hrp[2]

    @property
    def output(self):
    #    return HDG(self.hrp[0])
        return CMP("{},{},{},{}".format(self.mag,self.hrp[0],self.magh,self.fuseh.heading))


class TCCompass:

    def __init__(self, imu, hmc_side=1):
        # load configuration file
        with open('calibration.conf', mode='r') as f:
            mpu_conf = f.readline()
            lsm_conf = f.readline()
            mcnf = pickle.loads(mpu_conf)
            lcnf = pickle.loads(lsm_conf)
        self.MPU_Centre = mcnf[0][0]
        self.MPU_TR = mcnf[1]
        self.LSM_Centre = mcnf[0][0]
        self.LSM_TR = mcnf[1]
        self.counter = pyb.millis()

        # setup compasses

        # MPU9250
        self.imu = imu

        # LSM303
        self.lsm = LSM303.TiltCompCompass(hmc_side)
        self.lsm.setDeclination(0)
        self.lsm.setContinuousMode()

        self.gyrobias = (-1.394046, 1.743511, 0.4735878)

        # setup fusions
        self.fuse = Fusion()
        self.fuseh = Fusion()#TODO: temp for comparison
        self.update()
        self.hrp = [self.fuse.heading, self.fuse.roll, self.fuse.pitch]

    def process(self):
        self.update()
        if pyb.elapsed_millis(self.counter) >= 1000:
            self.hrp = [self.fuse.heading, self.fuse.roll, self.fuse.pitch]
            self.counter = pyb.millis()
            return True
        return False

    def update(self):
        accel = self.imu.accel.xyz
        gyroraw = self.imu.gyro.xyz

        gyro = [gyroraw[0] - self.gyrobias[0], gyroraw[1] - self.gyrobias[1], gyroraw[2] - self.gyrobias[2]]

        self.mag = self.imu.mag.xyz
        self.magh = self.lsm.getAxes()


        self.fuse.update(accel, gyro, self.adjust_mag(self.mag, self.MPU_Centre, self.MPU_TR))
        self.fuseh.update(accel, gyro, self.adjust_mag(self.magh, self.LSM_Centre, self.LSM_TR))

    def getmag(self):
        return self.imu.mag.xyz

    @staticmethod
    def adjust_mag(mag, centre, TR):
        mx_raw = mag[0] - centre[0]
        my_raw = mag[1] - centre[1]
        mz_raw = mag[2] - centre[2]

        mx = mx_raw * TR[0][0] + my_raw * TR[0][1] + mz_raw * TR[0][2]
        my = mx_raw * TR[1][0] + my_raw * TR[1][1] + mz_raw * TR[1][2]
        mz = mx_raw * TR[2][0] + my_raw * TR[2][1] + mz_raw * TR[2][2]
        return(mx,my,mz)

    def Calibrate(self):
        print("Calibrating. Press switch when done.")
        sw = pyb.Switch()
        self.fuse.calibrate(self.getmag, sw, lambda: pyb.delay(100))
        print(self.fuse.magbias)

    def gyrocal(self):
        xa=0
        ya=0
        za=0
        for x in range(0,100):
            xyz=self.imu.gyro.xyz
            xa+=xyz[0]
            ya+=xyz[1]
            za+=xyz[2]
            pyb.delay(1000)
        print(xa/100,ya/100,za/100)

    # def view(self):
    #     while True:
    #         self.update()
    #         print("{0}    {1}".format(self.fuse.heading, self.fuseh.heading))

    @property
    def heading(self):
        return self.hrp[0]

    @property
    def roll(self):
        return self.hrp[1]

    @property
    def pitch(self):
        return self.hrp[2]

    @property
    def output(self):
        outstring = [CMP("{},{},{},{}".format(self.mag, self.hrp[0], self.magh, self.fuseh.heading)).msg,
                     HDG(self.hrp[0]).msg]
        return outstring


def cthread(out_buf):
    imu = MPU9250('X')
    global i2c_object
    i2c_object = imu._mpu_i2c
    yield 0.03                                  # Allow accelerometer to settle
    compass = TCCompass(imu)

    while True:
        yield
        try:
            if compass.process():
                out_buf.write(compass.output)
        except:
            out_buf.write('compass error')

# def usertest():
#     imu=MPU9250('X')
#     c=TiltCompensatedCompass(imu)
#     c.Calibrate()
#
# # USER TEST PROGRAM
#
# def test(duration=0):
#     if duration:
#         print("Output accelerometer values for {:3d} seconds".format(duration))
#     else:
#         print("Output accelerometer values")
#     objSched = Sched()
#     objSched.add_thread(cthread())
#     if duration:
#         objSched.add_thread(stop(duration, objSched))           # Run for a period then stop
#     objSched.run()
#
#
# def compare():
#     imu=MPU9250('X')
#     hml=compy.compass(2)
#     hml.setDeclination(0)
#     hml.setContinuousMode()
#     print("Calibrating. Press switch when done.")
#     sw = pyb.Switch()
# #    self.fuse.calibrate(self.getmag, sw, lambda : pyb.delay(100))
# #    print(self.fuse.magbias)
#
#     while not sw():
#         print("{0},{1}".format(imu.mag.xyz,hml.getAxes()))
#
#
# def cthreaddev(link=None):
#     imu = MPU9250('X')
#     global i2c_object
#     i2c_object = imu._mpu_i2c
#     yield from wait(0.03)                                   # Allow accelerometer to settle
#     compass = TiltCompensatedCompass(imu)
#     wf = Poller(compass.poll, (4,), 1)                        # Instantiate a Poller with 1 second timeout.
#     hml=compy.compass(2) #TODO: chnage to 1 when we get them on same I2C bus?
#     hml.setDeclination(0)
#     hml.setContinuousMode()
#
#     while True:
#         reason = (yield wf())
#         if link is None:
#             with open('\sd\compass.dat','a') as f:
#                 f.write('{0} {1}\n'.format(imu.mag.xyz, hml.getAxes()))
#             print("Value heading:{:3f} roll:{:3f} pitch:{:3f}".format(compass.heading, compass.roll, compass.pitch))
#             print('{0} {1}\n'.format(imu.mag.xyz, hml.getAxes()))
#         else:
#             #TODO create output to serial port
#             print(compass.output.msg)
#
#
# #test(30)
#
# # imu = MPU9150('X')
# #
# # fuse = Fusion()
# #
# #
# # # Choose test to run
# # Calibrate = True
# # Timing = False
# #
# # def getmag():                               # Return (x, y, z) tuple (blocking read)
# #     return imu.mag.xyz
# #
# # if Calibrate:
# #     print("Calibrating. Press switch when done.")
# #     sw = pyb.Switch()
# #     fuse.calibrate(getmag, sw, lambda : pyb.delay(100))
# #     print(fuse.magbias)
# #
# # if Timing:
# #     mag = imu.mag.xyz # Don't include blocking read in time
# #     accel = imu.accel.xyz # or i2c
# #     gyro = imu.gyro.xyz
# #     start = pyb.micros()
# #     fuse.update(accel, gyro, mag) # 1.65mS on Pyboard
# #     t = pyb.elapsed_micros(start)
# #     print("Update time (uS):", t)
# #
# # count = 0
# # while True:
# #     fuse.update(imu.accel.xyz, imu.gyro.xyz, imu.mag.xyz) # Note blocking mag read
# #     if count % 50 == 0:
# #         print("Heading, Pitch, Roll: {:7.3f} {:7.3f} {:7.3f}".format(fuse.heading, fuse.pitch, fuse.roll))
# #     pyb.delay(20)
# #     count += 1
