#!/usr/bin/env python
"""
========================= job-panda.py ========================
A cute and adorable way to do various low-energy processing tasks.

The functions are arranged mostly sequentially, i.e. this file
documents the "procedure" necessary to produce LAT data,
starting from running skim_mjd_data.

====================== C. Wiseman, B. Zhu =====================
"""
import sys, shlex, glob, os, re, time
import subprocess as sp
import DataSetInfo as ds

# jobStr = "sbatch slurm-job.sh" # SLURM mode
jobStr = "sbatch pdsf.slr" # SLURM+Shifter mode
jobQueue = latDir+"/job.queue"

# =============================================================
def main(argv):

    # defaults
    global useJobQueue
    dsNum, subNum, runNum, argString, calList, useJobQueue = None, None, None, None, [], False

    # loop over user args
    for i,opt in enumerate(argv):

        # set queue mode
        if opt == "-q": useJobQueue = True

        # set ds, sub, cal
        if opt == "-ds":  dsNum = int(argv[i+1])
        if opt == "-sub": dsNum, subNum = int(argv[i+1]), int(argv[i+2])
        if opt == "-run": dsNum, runNum = int(argv[i+1]), int(argv[i+2])
        if opt == "-cal": calList = getCalRunList(dsNum,subNum,runNum)

        # these all potentially depend on a calibration list being used
        if opt == "-skim":      runSkimmer(dsNum, subNum, runNum, calList=calList)
        if opt == "-wave":      runWaveSkim(dsNum, subNum, runNum, calList=calList)
        if opt == "-qsubSplit": qsubSplit(dsNum, subNum, runNum, calList=calList)
        if opt == "-writeCut":  writeCut(dsNum, subNum, runNum, calList=calList)
        if opt == "-lat":       runLAT(dsNum, subNum, runNum, calList=calList)
        if opt == "-pandify":   pandifySkim(dsNum, subNum, runNum, calList=calList)

        # mega modes
        if opt == "-megaLAT":   [runLAT(i) for i in range(0,5+1)]
        if opt == "-megaSkim":  [runSkimmer(i) for i in range(0,5+1)]
        if opt == "-megaWave":  [runWaveSkim(i) for i in range(0,5+1)]
        if opt == "-megaSplit": [qsubSplit(i) for i in range(0,5+1)]
        if opt == "-megaCut":   [writeCut(i) for i in range(0,5+1)]

        # misc
        if opt == "-split":        splitTree(dsNum, subNum, runNum)
        if opt == "-checkLogs":    checkLogErrors()
        if opt == "-checkLogs2":   checkLogErrors2()
        if opt == "-skimLAT":      skimLAT(argv[i+1],argv[i+2],argv[i+3])
        if opt == "-tuneCuts":     tuneCuts(argv[i+1],dsNum)
        if opt == "-lat3":         applyCuts(int(argv[i+1]),argv[i+2])
        if opt == "-cron":         cronJobs()
        if opt == "-shifter":      shifterTest()
        if opt == "-test":         quickTest()

        # process systematic study runs
        if opt == "-sskim":  specialSkim()
        if opt == "-swave":  specialWave()
        if opt == "-ssplit": specialSplit()
        if opt == "-splitf": splitFile(argv[i+1],argv[i+2])
        if opt == "-sdel":   specialDelete()
        if opt == "-slat":   specialLAT()
        if opt == "-scheck": specialCheck()


# =============================================================

def sh(cmd):
    """ Either call the shell or put the command in our cron queue.
        Uses the global bool 'useJobQueue' and the global path 'jobQueue'.
    """
    if not useJobQueue:
        sp.call(shlex.split(cmd))
        return

    with open(jobQueue, 'a+') as f:
        if cmd not in open(jobQueue).read():
            print("+cron.queue: %s" % (cmd))
            f.write(cmd + "\n")


def getCalRunList(dsNum=None,subNum=None,runNum=None):
    """ ./job-panda.py -cal (-ds [dsNum] -sub [dsNum] [calIdx] -run [runNum])
        Create a calibration run list, using the CalInfo object in DataSetInfo.py .
        Note that the -sub option is re-defined here to mean a calibration range idx.
        Note that running with -cal alone will create a list for all datasets (mega mode).
    """
    runLimit = 10 # yeah I'm hardcoding this, sue me.
    calList = []
    calInfo = ds.CalInfo()
    calKeys = calInfo.GetKeys(dsNum)

    # single-run mode
    if runNum!=None:
        calList.append(runNum)
        print(calList)
        return calList

    # multi-run mode:
    for key in calKeys:
        print("key:",key)

        # -cal (mega mode)
        if dsNum==None:
            for idx in range(calInfo.GetIdxs(key)):
                lst = calInfo.GetCalList(key,idx,runLimit)
                print(lst)
                calList += lst
        # -ds
        elif subNum==None:
            for idx in range(calInfo.GetIdxs(key)):
                lst = calInfo.GetCalList(key,idx,runLimit)
                print(lst)
                calList += lst
        # -sub
        else:
            lst = calInfo.GetCalList(key,subNum,runLimit)
            if lst==None: continue
            print(lst)
            calList += lst

    # remove any duplicates, but there probably aren't any
    calList = sorted(list(set(calList)))

    return calList


def runSkimmer(dsNum, subNum=None, runNum=None, calList=[]):
    """ ./job-panda.py -skim (-ds dsNum) (-sub dsNum subNum) (-run dsNum subNum) [-cal]
        Submit skim_mjd_data jobs.
    """
    # bg
    if not calList:
        # -ds
        if subNum==None and runNum==None:
            for i in range(ds.dsMap[dsNum]+1):
                sh("""%s './skim_mjd_data %d %d -n -l -t 0.7 %s'""" % (jobStr, dsNum, i, ds.skimDir))
        # -sub
        elif runNum==None:
            sh("""%s './skim_mjd_data %d %d -n -l -t 0.7 %s'""" % (jobStr, dsNum, subNum, ds.skimDir))
        # -run
        elif subNum==None:
            sh("""%s './skim_mjd_data -f %d -n -l -t 0.7 %s'""" % (jobStr, runNum, ds.skimDir))
    # cal
    else:
        for run in calList:
            sh("""%s './skim_mjd_data -f %d -n -l -t 0.7 %s'""" % (jobStr, run, ds.calDir))


def runWaveSkim(dsNum, subNum=None, runNum=None, calList=[]):
    """ ./job-panda.py -wave (-ds dsNum) (-sub dsNum subNum) (-run dsNum subNum) [-cal]
        Submit wave-skim jobs.
    """
    # bg
    if not calList:
        # -ds
        if subNum==None and runNum==None:
            for i in range(ds.dsMap[dsNum]+1):
                sh("""%s './wave-skim -n -r %d %d -p %s %s'""" % (jobStr, dsNum, i, ds.skimDir, ds.waveDir) )
        # -sub
        elif runNum==None:
            sh("""%s './wave-skim -n -r %d %d -p %s %s'""" % (jobStr, dsNum, subNum, ds.skimDir, ds.waveDir) )
        # -run
        elif subNum==None:
            sh("""%s './wave-skim -n -f %d %d -p %s %s""" % (jobStr, dsNum, runNum, ds.skimDir, ds.waveDir) )
    # cal
    else:
        for run in calList:
            for key in ds.dsRanges:
                if ds.dsRanges[key][0] <= run <= ds.dsRanges[key][1]:
                    dsNum=key
            sh("""%s './wave-skim -n -c -f %d %d -p %s %s'""" % (jobStr, dsNum, run, ds.calSkimDir, ds.calWaveDir) )


def getFileList(filePathRegexString, subNum, uniqueKey=False, dsNum=None):
    """ Creates a dict of files w/ the format {'DSX_X_X':filePath.}
        Used to combine and split apart files during the LAT processing.
        Used by: splitTree, writeCut, runLAT.
    """
    files = {}
    for fl in glob.glob(filePathRegexString):
        int(re.search(r'\d+',fl).group())
        ints = map(int, re.findall(r'\d+',fl))
        if (ints[1]==subNum):
            if (len(ints)==2):
                ints.append(0)
            if not uniqueKey:
                files[ints[2]] = fl # zero index
            else:
                files["DS%d_%d_%d" % (dsNum,subNum,ints[2])] = fl
    return files


def splitTree(dsNum, subNum=None, runNum=None):
    """ ./job-panda.py -split (-sub dsNum subNum) (-run dsNum runNum)

        Split a SINGLE waveSkim file into small (~50MB) files to speed up LAT parallel processing.
        Can call 'qsubSplit' instead to submit each run in the list as a job, splitting the files in parallel.
        NOTE: The cut written into the first file is NOT copied into the additional files
              (I couldnt get it to work within this function -- kept getting "file not closed" errors.)
              To clean up, do that with the 'writeCut' function below, potentially AFTER a big parallel job.
    """
    from ROOT import TFile, TTree, gDirectory, TEntryList, TNamed, TObject, gROOT

    # Set input and output paths.  Clear out any files from a previous
    # try before you attempt a copy (avoid the double underscore)
    inPath, outPath = "", ""
    if runNum==None:
        # bg mode
        inPath = "%s/waveSkimDS%d_%d.root" % (ds.waveDir,dsNum,subNum)
        outPath = "%s/split/splitSkimDS%d_%d.root" % (ds.waveDir,dsNum,subNum)
        fileList = getFileList("%s/split/splitSkimDS%d_%d*.root" % (ds.waveDir,dsNum,subNum),subNum)
        for key in fileList: os.remove(fileList[key])
    elif subNum==None:
        # cal mode
        inPath = "%s/waveSkimDS%d_run%d.root" % (ds.calWaveDir,dsNum,runNum)
        outPath = "%s/split/splitSkimDS%d_run%d.root" % (ds.calWaveDir,dsNum,runNum)
        fileList = getFileList("%s/split/splitSkimDS%d_run%d*.root" % (ds.calWaveDir,dsNum,runNum),runNum)
        for key in fileList: os.remove(fileList[key])

    inFile = TFile(inPath)
    bigTree = inFile.Get("skimTree")
    theCut = inFile.Get("theCut").GetTitle()
    bigTree.Draw(">>elist",theCut,"entrylist")
    elist = gDirectory.Get("elist")
    bigTree.SetEntryList(elist)
    nList = elist.GetN()

    outFile = TFile(outPath,"RECREATE")
    lilTree = TTree()
    lilTree.SetMaxTreeSize(50000000) # 50 MB
    thisCut = TNamed("theCut",theCut)
    thisCut.Write("",TObject.kOverwrite)
    lilTree = bigTree.CopyTree("") # this does NOT write the cut into the extra files
    lilTree.Write("",TObject.kOverwrite)


def qsubSplit(dsNum, subNum=None, runNum=None, calList=[]):
    """ ./job-panda.py -qsubSplit (-ds dsNum) (-sub dsNum subNum) (-run dsNum subNum) [-cal]
        Submit jobs that call splitTree for each run, splitting files into small (~100MB) chunks.
        NOTE: The data cleaning cut is NOT written into the output files and the
              function 'writeCut' must be called after these jobs are done.
    """
    from shutil import copyfile

    # bg
    if not calList:
        # -ds
        if subNum==None and runNum==None:
            for i in range(ds.dsMap[dsNum]+1):
                inPath = "%s/waveSkimDS%d_%d.root" % (ds.waveDir,dsNum,i)
                if not os.path.isfile(inPath):
                    print("File",inPath,"not found. Continuing ...")
                    continue
                if (os.path.getsize(inPath)/1e6 < 45):
                    copyfile(inPath, "%s/splitSkimDS%d_%d.root" % (ds.splitDir, dsNum, i))
                else:
                    sh("""%s './job-panda.py -split -sub %d %d'""" % (jobStr, dsNum, i))
        # -sub
        elif runNum==None:
            inPath = "%s/waveSkimDS%d_%d.root" % (ds.waveDir,dsNum,subNum)
            if not os.path.isfile(inPath):
                print("File",inPath,"not found.")
                return
            if (os.path.getsize(inPath)/1e6 < 45):
                copyfile(inPath, "%s/splitSkimDS%d_%d.root" % (ds.splitDir, dsNum, subNum))
            else:
                sh("""%s './job-panda.py -split -sub %d %d'""" % (jobStr, dsNum, subNum))
        # -run
        elif subNum==None:
            inPath = "%s/waveSkimDS%d_run%d.root" % (ds.waveDir,dsNum,runNum)
            if not os.path.isfile(inPath):
                print("File",inPath,"not found.")
                return
            if (os.path.getsize(inPath)/1e6 < 45):
                copyfile(inPath, "%s/splitSkimDS%d_%d.root" % (ds.splitDir, dsNum, runNum))
            else:
                sh("""%s './job-panda.py -split -run %d %d'""" % (jobStr, dsNum, runNum))
    # cal
    else:
        for run in calList:
            for key in ds.dsRanges:
                if ds.dsRanges[key][0] <= run <= ds.dsRanges[key][1]:
                    dsNum=key
            inPath = "%s/waveSkimDS%d_run%d.root" % (ds.calWaveDir,dsNum,run)
            if not os.path.isfile(inPath):
                print("File",inPath,"not found. Continuing ...")
                continue
            if (os.path.getsize(inPath)/1e6 < 45):
                copyfile(inPath, "%s/splitSkimDS%d_run%d.root" % (ds.calSplitDir, dsNum, run))
            else:
                sh("""%s './job-panda.py -split -run %d %d'""" % (jobStr, dsNum, run))


def writeCut(dsNum, subNum=None, runNum=None, calList=[]):
    """ ./job-panda.py -writeCut (-ds dsNum) (-sub dsNum subNum) (-run dsNum subNum) [-cal]
        Assumes the cut used in the FIRST file (even in the whole DS) should be applied
        to ALL files.  This should be a relatively safe assumption.
    """
    from ROOT import TFile, TNamed, TObject
    mainList = {}

    # bg
    if not calList:
        # -ds
        if subNum==None and runNum==None:
            for i in range(ds.dsMap[dsNum]+1):
                inPath = "%s/splitSkimDS%d_%d*" % (ds.splitDir,dsNum,i)
                fileList = getFileList(inPath,i,True,dsNum)
                mainList.update(fileList)
        # -sub
        elif runNum==None:
            inPath = "%s/splitSkimDS%d_%d*" % (ds.splitDir,dsNum,subNum)
            fileList = getFileList(inPath,subNum,True,dsNum)
            mainList.update(fileList)
        # -run
        elif subNum==None:
            inPath = "%s/splitSkimDS%d_run%d*" % (ds.splitDir,dsNum,runNum)
            fileList = getFileList(inPath,runNum,True,dsNum)
            mainList.update(fileList)
    # cal
    else:
        for run in calList:
            for key in ds.dsRanges:
                if ds.dsRanges[key][0] <= run <= ds.dsRanges[key][1]:
                    dsNum=key
            inPath = "%s/splitSkimDS%d_run%d*" % (ds.calSplitDir,dsNum,run)
            fileList = getFileList(inPath,run,True,dsNum)
            mainList.update(fileList)

    # Pull the cut off the FIRST file and add it to the sub-files
    if len(mainList) <= 1:
        print("No files found!  Exiting...")
        exit(1)
    theCut = ""
    foundFirst = False
    for key, inFile in sorted(mainList.items()):
        if not foundFirst:
            firstFile = TFile(mainList[key])
            theCut = firstFile.Get("theCut").GetTitle()
            print("Applying this cut:\n",theCut)
            foundFirst = True
        print(key, inFile)
        subRangeFile = TFile(inFile,"UPDATE")
        thisCut = TNamed("theCut",theCut)
        thisCut.Write("",TObject.kOverwrite)


def runLAT(dsNum, subNum=None, runNum=None, calList=[]):
    """ ./job-panda.py -lat (-ds dsNum) (-sub dsNum subNum) (-run dsNum subNum) [-cal]
        Runs LAT on splitSkim output.  Does not combine output files back together.
    """
    # bg
    if not calList:
        # -ds
        if subNum==None and runNum==None:
            for i in range(ds.dsMap[dsNum]+1):
                files = getFileList("%s/splitSkimDS%d_%d*" % (ds.splitDir,dsNum,i),i)
                for idx, inFile in sorted(files.items()):
                    outFile = "%s/latSkimDS%d_%d_%d.root" % (ds.latDir,dsNum,i,idx)
                    sh("""%s './lat.py -b -r %d %d -p %s %s'""" % (jobStr,dsNum,i,inFile,outFile))
        # -sub
        elif runNum==None:
            files = getFileList("%s/splitSkimDS%d_%d*" % (ds.splitDir,dsNum,subNum),subNum)
            for idx, inFile in sorted(files.items()):
                outFile = "%s/latSkimDS%d_%d_%d.root" % (ds.latDir,dsNum,subNum,idx)
                sh("""%s './lat.py -b -r %d %d -p %s %s'""" % (jobStr,dsNum,subNum,inFile,outFile))
        # -run
        elif subNum==None:
            files = getFileList("%s/splitSkimDS%d_run%d*" % (ds.splitDir,dsNum,runNum),runNum)
            for idx, inFile in sorted(files.items()):
                outFile = "%s/latSkimDS%d_run%d_%d.root" % (ds.latDir,dsNum,runNum,idx)
                sh("""%s './lat.py -b -f %d %d -p %s %s'""" % (jobStr,dsNum,runNum,inFile,outFile))
    # cal
    else:
        for run in calList:
            for key in ds.dsRanges:
                if ds.dsRanges[key][0] <= run <= ds.dsRanges[key][1]:
                    dsNum=key
            files = getFileList("%s/splitSkimDS%d_run%d*" % (ds.calSplitDir,dsNum,run),run)
            for idx, inFile in sorted(files.items()):
                outFile = "%s/latSkimDS%d_run%d_%d.root" % (ds.calLatDir,dsNum,run,idx)
                sh("""%s './lat.py -b -f %d %d -p %s %s'""" % (jobStr,dsNum,run,inFile,outFile))


def mergeLAT():
    """ It seems like a good idea, right?
        Merging all the LAT files back together after splitting?
    """
    print("hey")


def checkLogErrors():
    """ ./job-panda.py -checkLogs
        This isn't really complete. but you get the idea.  Error checking via bash inside python is kind of a PITA.
        Maybe it would be better to just have python look at the files directly.
    """

    # Shell commands
    c1 = "ls -F ./logs/ | grep -v / | wc -l" # count total files
    c2 = "grep -rIl \"Done! Job Panda\" ./logs/ | wc -l" # count completed files
    c3 = "grep -rL \"Done! Job Panda\" ./logs/"  # negative file matching, can also count # fails.  gives a file list
    c4 = "grep -rIl \"Segmentation\" ./logs/" # segfaults
    c5 = "grep -rIl \"bad_alloc\" ./logs/" # memory errors

    # using sp to deal with a pipe is kind of annoying
    p1 = sp.Popen('ls -F ./logs/'.split(), stdout=sp.PIPE)
    p2 = sp.Popen('grep -v /'.split(), stdin=p1.stdout, stdout=sp.PIPE)
    p3 = sp.Popen('wc -l'.split(), stdin=p2.stdout,stdout=sp.PIPE)
    output = p3.communicate()[0]
    num = int(output.strip('\n'))
    print(num)

    # make a dummy bash script that runs all the shell commands.  who knows if this is smart or not
    outFile = open('logCheck.sh','w+')
    dummyScript = "#!/bin/bash \n %s \n %s \n %s \n %s \n %s \n" % (c1,c2,c3,c4,c5)
    outFile.write(dummyScript)
    outFile.close()
    sh('chmod a+x logCheck.sh')
    sh('./logCheck.sh')
    os.remove('logCheck.sh')


def checkLogErrors2():
    """ Usage: ./job-panda -checkLogs2
        Globs together log files and then searches for "Error", returning the failed ROOT files.
    """
    print("Checking log errors ...")

    ErrList = []
    for fl in glob.glob("./logs/*"):
        fErr = open(fl,'r').read()
        if 'Error' in open(fl, 'r').read():
            print(ErrList.append(fl))

    for errFile in ErrList:
        fErr = open(errFile,'r')
        for lineErr in fErr:
            if '/lat.py -b' in lineErr:
                print('Error from: ', lineErr)
            if 'Error' in lineErr:
                print(lineErr)


def tuneCuts(argString, dsNum=None):
    """ ./job-panda.py -tuneCuts '[argString]' -- run over all ds's
        ./job-panda.py -ds [dsNum] -tuneCuts '[argString]' -- just one DS

    Submit a bunch of lat3.py jobs to the queues.
    NOTE:
        1) If processing individual dataset, the -ds option MUST come before -tuneCuts.
        2) Make sure to put argString in quotes.
        3) argString may be multiple options separated by spaces

    Options for argString:
        -all, -bcMax, -noiseWeight, -bcTime, -tailSlope, -fitSlo, -riseNoise
    """
    calInfo = ds.CalInfo()
    if dsNum==None:
        for i in ds.dsMap.keys():
            if i == 6: continue
            for mod in [1,2]:
                try:
                    for j in range(calInfo.GetIdxs("ds%d_m%d"%(i, mod))):
                        print("%s './lat3.py -db -tune %s -s %d %d %d %s" % (jobStr, ds.calLatDir, i, j, mod, argString))
                        sh("""%s './lat3.py -db -tune %s -s %d %d %d %s '""" % (jobStr, ds.calLatDir, i, j, mod, argString))
                except: continue
    # -ds
    else:
        for mod in [1,2]:
            try:
                for j in range(calInfo.GetIdxs("ds%d_m%d"%(dsNum, mod))):
                    print("%s './lat3.py -db -tune %s -s %d %d %d %s" % (jobStr, ds.calLatDir, dsNum, j, mod, argString))
                    sh("""%s './lat3.py -db -tune %s -s %d %d %d %s '""" % (jobStr, ds.calLatDir, dsNum, j, mod, argString))
            except: continue


def applyCuts(dsNum, cutType):
    """ ./job-panda.py -lat3 [dsNum] [cutType]"""

    if dsNum==-1:
        for ds in range(6):
            sh("""%s './lat3.py -cut %d %s'""" % (jobStr, ds, cutType))
    else:
        sh("""%s './lat3.py -cut %d %s'""" % (jobStr, dsNum, cutType))



def pandifySkim(dsNum, subNum=None, runNum=None, calList=[]):
    """ ./job-panda.py -pandify (-ds dsNum) (-sub dsNum subNum) (-run dsNum subNum) [-cal]
        Run ROOTtoPandas jobs.
    """
    # bg
    if not calList:
        # -ds
        if subNum==None and runNum==None:
            for i in range(ds.dsMap[dsNum]+1):
                sh("""%s 'python3 ./sandbox/ROOTtoPandas.py -ws %d %d -p -d %s %s'""" % (jobStr, dsNum, i, ds.waveDir, ds.pandaDir))
        # -sub
        elif runNum==None:
            sh("""%s 'python3 ./sandbox/ROOTtoPandas.py -ws %d %d -p -d %s %s'""" % (jobStr, dsNum, subNum, ds.waveDir, ds.pandaDir))
        # -run
        elif subNum==None:
            sh("""%s 'python3 ./sandbox/ROOTtoPandas.py -f %d %d -p -d %s %s'""" % (jobStr, dsNum, runNum, ds.waveDir, ds.pandaDir))
    # cal
    else:
        for i in calList:
            sh("""%s 'python3 ./sandbox/ROOTtoPandas.py -f %d %d -p -d %s %s'""" % (jobStr, dsNum, i, ds.calWaveDir, ds.pandaDir))


def cronJobs():
    """ ./job-panda.py -cron
    Uses the global string 'jobQueue'.
    Crontab should contain the following lines (crontab -e):
    SHELL=/bin/bash
    MAILTO="" # can put in some address here if you LOVE emails
    #*/10 * * * * source ~/env/EnvBatch.sh; ~/lat/job-panda.py -cron >> ~/lat/cron.log 2>&1
    """
    os.chdir(home+"/lat/")
    print("Cron:",time.strftime('%X %x %Z'),"cwd:",os.getcwd())

    nMaxRun, nMaxPend = 15, 200

    with open(jobQueue) as f:
        jobList = [line.rstrip('\n') for line in f]
    nList = len(jobList)

    status = os.popen('slusers | grep wisecg').read()
    status = status.split()
    nRun = int(status[0]) if len(status) > 0 else 0  # Rjob Rcpu Rcpu*h PDjob PDcpu user:account:partition
    nPend = int(status[3]) if len(status) > 0 else 0

    nSubmit = (nMaxRun-nRun) if nRun < nMaxRun else 0
    nSubmit = nList if nList < nSubmit else nSubmit
    nSubmit = 0 if nPend >= nMaxPend else nSubmit

    print("   nRun %d  (max %d)  nPend %d (max %d)  nList %d  nSubmit %d" % (nRun,nMaxRun,nPend,nMaxPend,nList,nSubmit))

    with open(jobQueue, 'w') as f:
        for idx, job in enumerate(jobList):
            if idx < nSubmit:
                print("Submitted:",job)
                sh(job)
            else:
                # print("Waiting:", job)
                f.write(job + "\n")


def shifterTest():
    """ ./job-panda.py -shifter """
    print("Shifter:",time.strftime('%X %x %Z'),"cwd:",os.getcwd())
    sh("""sbatch shifter.slr 'python sandbox/bl2.py'""")


def specialSkim():
    """ ./job-panda.py [-q (use cron queue)] -sskim """
    cal = ds.CalInfo()
    # runList = cal.GetSpecialRuns("extPulser")
    # runList = cal.GetSpecialRuns("delayedTrigger")
    runList = cal.GetSpecialRuns("longCal",5)
    # run = runList[0]
    # sh("""%s './skim_mjd_data -x -l -f %d %s/skim'""" % (jobStr,run,ds.specialDir))
    for run in runList:

        if useJobQueue:
            # this is what you would want for a normal cron queue
            # sh("""./lat.py -x -b -f %d %d -p %s %s""" % (dsNum, run, inFile, outFile))

            # this is what i need for a 1-node job pump
            # sh("""./lat.py -x -b -f %d %d -p %s %s >& ./logs/extPulser-%d.txt""" % (dsNum, run, inFile, outFile, run))
            sh("""./skim_mjd_data %d %d -n -l -t 0.7 %s""" % (jobStr, dsNum, i, skimDir))



        print(run)
        # sh("""%s './skim_mjd_data -x -l -f %d %s/skim'""" % (jobStr,run,ds.specialDir))



def specialWave():
    """ ./job-panda.py -swave """
    cal = ds.CalInfo()
    # runList = cal.GetSpecialRuns("extPulser")
    runList = cal.GetSpecialRuns("delayedTrigger")
    # sh("""./wave-skim -x -n -f %d %d -p %s/skim %s/waves""" % (0, runList[0], ds.specialDir, ds.specialDir) )
    for run in runList:
        sh("""%s './wave-skim -x -n -f %d %d -p %s/skim %s/waves'""" % (jobStr, ds.GetDSNum(run), run, ds.specialDir, ds.specialDir) )


def specialSplit():
    """ ./job-panda.py -ssplit
    External pulser runs have no data cleaning cut.
    Has a memory leak (can't close both TFiles, damn you, ROOT); submit each run as a batch job.
    """
    from ROOT import TFile, TTree, TObject

    cal = ds.CalInfo()
    runList = cal.GetSpecialRuns("extPulser")
    for run in runList:
        print(run)
        if run <= 4592: continue

        inPath = "%s/waves/waveSkimDS%d_run%d.root" % (ds.specialDir, ds.GetDSNum(run), run)
        outPath = "%s/split/splitSkimDS%d_run%d.root" % (ds.specialDir, ds.GetDSNum(run), run)

        outFiles = glob.glob("%s/split/splitSkimDS%d_run%d*.root" % (ds.specialDir, ds.GetDSNum(run), run))
        for filename in outFiles:
            try:
                os.remove(filename)
            except OSError:
                pass

        sh("""%s './job-panda.py -splitf %s %s'""" % (jobStr,inPath, outPath))


def splitFile(inPath,outPath):
    """ ./job-panda.py -splitf [inPath] [outPath]
    Used by specialSplit. """
    from ROOT import TFile, TTree, TObject
    inFile = TFile(inPath)
    bigTree = inFile.Get("skimTree")
    outFile = TFile(outPath, "RECREATE")
    lilTree = TTree()
    lilTree.SetMaxTreeSize(30000000) # 30MB
    lilTree = bigTree.CopyTree("")
    lilTree.Write("",TObject.kOverwrite)


def specialDelete():
    """./job-panda.py -sdel"""

    # remove all files from ext pulser range
    cal = ds.CalInfo()
    for idx in [6]:
        runList = cal.GetSpecialRuns("extPulser",idx)
        for run in runList:
            outFiles = glob.glob("%s/split/splitSkimDS%d_run%d*.root" % (ds.specialDir, ds.GetDSNum(run), run))
            outFiles.extend(["%s/skim/skimDS%d_run%d_low.root" % (ds.specialDir, ds.GetDSNum(run), run)])
            outFiles.extend(["%s/waves/waveSkimDS%d_run%d.root" % (ds.specialDir, ds.GetDSNum(run), run)])
            outFiles.extend(glob.glob("%s/lat/latSkimDS%d_run%d_*.root" % (ds.specialDir, ds.GetDSNum(run), run)))
            for filename in outFiles:
                print(filename)
                try:
                    os.remove(filename)
                except OSError:
                    pass

    # remove lat files without the _X.root
    # import datetime
    # cal = ds.CalInfo()
    # runList = cal.GetSpecialRuns("extPulser")
    # for run in runList:
    #     outFile = "%s/lat/latSkimDS%d_run%d.root" % (ds.specialDir, ds.GetDSNum(run), run)
    #     try:
    #         modDate = os.path.getmtime(outFile)
    #         modDate = datetime.datetime.fromtimestamp(int(modDate)).strftime('%Y-%m-%d %H:%M:%S')
    #         print(outFile, modDate)
    #         os.remove(outFile)
    #     except OSError:
    #         pass


def specialLAT():
    """ ./job-panda.py [-q (use cron queue)] -slat"""
    cal = ds.CalInfo()
    runList = cal.GetSpecialRuns("extPulser")

    # deal with unsplit files
    # run = runList[0]
    # dsNum = ds.GetDSNum(run)
    # inFile = "%s/waves/waveSkimDS%d_run%d.root" % (ds.specialDir,dsNum,run)
    # outFile = "%s/lat/latSkimDS%d_run%d.root" % (ds.specialDir,dsNum,run)
    # sh("""./lat.py -x -b -f %d %d -p %s %s""" % (dsNum,run,inFile,outFile))

    # deal with split files
    for run in runList:

        dsNum = ds.GetDSNum(run)
        inFiles = glob.glob("%s/split/splitSkimDS%d_run%d*.root" % (ds.specialDir, dsNum, run))
        for idx in range(len(inFiles)):
            if idx==0:
                inFile = "%s/split/splitSkimDS%d_run%d.root" % (ds.specialDir, dsNum, run)
            else:
                inFile = "%s/split/splitSkimDS%d_run%d_%d.root" % (ds.specialDir, dsNum, run, idx)
            if not os.path.isfile(inFile) :
                print("File doesn't exist:",inFile)
                return
            outFile = "%s/lat/latSkimDS%d_run%d_%d.root" % (ds.specialDir, dsNum, run, idx)

            if useJobQueue:
                # this is what you would want for a normal cron queue
                # sh("""./lat.py -x -b -f %d %d -p %s %s""" % (dsNum, run, inFile, outFile))

                # this is what i need for a 1-node job pump
                sh("""./lat.py -x -b -f %d %d -p %s %s >& ./logs/extPulser-%d.txt""" % (dsNum, run, inFile, outFile, run))
            else:
                sh("""%s './lat.py -x -b -f %d %d -p %s %s' """ % (jobStr, dsNum, run, inFile, outFile))


def specialCheck():
    """./job-panda.py -scheck
    A next step could be to 'hadd' split files back together, but we'll wait for now.
    """
    from ROOT import TFile, TTree
    cal = ds.CalInfo()
    runList = cal.GetSpecialRuns("extPulser")
    for run in runList:
        fileList = glob.glob("%s/lat/latSkimDS%d_run%d_*.root" % (ds.specialDir, ds.GetDSNum(run), run))
        for f in fileList:
            tf = TFile(f)
            tr = tf.Get("skimTree")
            print(f)
            print(tr.GetEntries())
            tr.GetEntry(0)
            tf.Close()


def quickTest():
    """./job-panda.py -test """
    # from ROOT import MGTWaveform, GATDataSet, TChain
    # import datetime, time
    # print("Sleeping 10 sec ...")
    # time.sleep(10)
    # now = datetime.datetime.now()
    # print("Done. Date: ",str(now))

    cal = ds.CalInfo()
    runList = cal.GetSpecialRuns("extPulser")
    print(runList)


if __name__ == "__main__":
    main(sys.argv[1:])

