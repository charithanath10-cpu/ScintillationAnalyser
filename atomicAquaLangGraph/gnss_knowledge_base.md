no # GNSS/NovAtel Comprehensive Knowledge Base

This knowledge base contains ALL extracted context from the codebase.

## Log Types

### ALIGNAUTOMATION

**Fields:**

- `comport`: uenumString (offset: 4)
- `headingextboption`: uenumString (offset: 16)
- `interfacemode`: uenumString (offset: 20)
- `option`: uenumString (offset: 0)

### APPLYVBR

**Fields:**

- `switch`: uenumString (offset: 0)

### ASSIGNLBANDBEAM

**Fields:**

- `name`: ustringvariable (offset: 4)
- `option`: uenumString (offset: 0)

### AUTHCODES

**Fields:**

- `authCodeString`: ustringvariable (offset: 16)
- `authCodeType`: uenumString (offset: 8)
- `signatureStatus`: uenumString (offset: 0)

### AUTOSURVEY

**Fields:**

- `accuracy`: ufloatString (offset: 8)
- `control`: uenumString (offset: 0)
- `save_nvm`: uenumString (offset: 16)
- `tolerance`: ufloatString (offset: 12)

### AVEPOS

**Fields:**

- `height`: udoubleString (offset: 16)
- `heightDeviation`: ufloatString (offset: 32)
- `latitude`: udoubleString (offset: 0)
- `latitudeDeviation`: ufloatString (offset: 24)
- `longitude`: udoubleString (offset: 8)
- `longitudeDeviation`: ufloatString (offset: 28)
- `posaveStatus`: uenumString (offset: 36)

### BASEANTENNAPCO

**Fields:**

- `eastOffset`: udoubleString (offset: 12)
- `frequency`: uenumString (offset: 0)
- `northOffset`: udoubleString (offset: 4)
- `upOffset`: udoubleString (offset: 20)

### BASEANTENNATYPE

**Fields:**

- `antennaType`: uenumString (offset: 0)
- `radomeType`: uenumString (offset: 4)

### BESTPOS

**Fields:**

- `CRC`: uhex (offset: 72)
- `datumId`: uenumString (offset: 36)
- `differentialAge`: ufloatString (offset: 56)
- `extendedSolutionStatus`: uhex (offset: 69)
- `height`: udoubleString (offset: 24)
- `heightDeviation`: ufloatString (offset: 48)
- `idleTime`: uhex (offset: 12)
- `latitude`: udoubleString (offset: 8)
- `latitudeDeviation`: ufloatString (offset: 40)
- `longitude`: udoubleString (offset: 16)
- `longitudeDeviation`: ufloatString (offset: 44)
- `positionType`: uenumString (offset: 4)
- `satellitesTracked`: ucharString (offset: 64)
- `satellitesUsed`: ucharString (offset: 65)
- `satellitesUsedInL1`: ucharString (offset: 66)
- `satellitesWithMultiFreqCount`: ucharString (offset: 67)
- `sentenceTerminator`: uhex (offset: 4)
- `signalMaskGalBds`: uhex (offset: 70)
- `signalMaskGpsGlo`: uhex (offset: 71)
- `solutionAge`: ufloatString (offset: 60)
- `solutionStatus`: uenumString (offset: 0)
- `undulation`: ufloatString (offset: 32)

### BESTSATS

**Fields:**

- `SignalMask`: uhex (offset: 16)
- `satelliteID`: uenumString (offset: 8)
- `status`: uenumString (offset: 12)
- `system`: uenumString (offset: 4)

### CONNECTIMU

**Fields:**

- `IMUPort`: uenumString (offset: 0)
- `IMUType`: uenumString (offset: 4)

### DNSCONFIG

**Fields:**

- `dnsserver`: uenumString (offset: 0)
- `ipAddress`: ustringvariable (offset: 4)

### DUALANTENNAALIGN

**Fields:**

- `switch`: uenumString (offset: 0)

### DUMMY

### FILELIST

**Fields:**

- `fileName`: ustringvariable (offset: 20)
- `fileType`: uenumString (offset: 4)
- `massStorageDevice`: uenumString (offset: 0)

### FILEROTATECONFIG

**Fields:**

- `diskFullAction`: uenumString (offset: 4)
- `maxFileSize`: ushortString (offset: 2)
- `maxFileTime`: ushortString (offset: 0)

### FILESYSTEMCAPACITY

**Fields:**

- `massStorageDevice`: uenumString (offset: 4)

### FILESYSTEMSTATUS

**Fields:**

- `errorMsg`: ustringvariable (offset: 12)
- `massStorageDevice`: uenumString (offset: 0)
- `massStorageStatus`: uenumString (offset: 4)

### FILETRANSFERSTATUS

**Fields:**

- `errorMsg`: ustringvariable (offset: 16)
- `fileName`: ustringvariable (offset: 12)
- `fileTransferStatus`: uenumString (offset: 0)

### GENERATEDIFF

**Fields:**

- `mode`: uenumString (offset: 0)
- `port`: uenumString (offset: 4)

### GENERATERTK

**Fields:**

- `mode`: uenumString (offset: 0)
- `port`: uenumString (offset: 4)

### GIIICARDSTATUS

**Fields:**

- `component`: uenumString (offset: 20)
- `fanFailed`: ushortString (offset: 6)
- `fanSpeed`: ushortString (offset: 4)
- `idleTime`: ufloatString (offset: 28)
- `mode`: ushortString (offset: 2)
- `moduleId`: ushortString (offset: 26)
- `slotId`: ushortString (offset: 24)
- `state`: ushortString (offset: 0)
- `value_1`: ufloatString (offset: 32)
- `value_2`: ufloatString (offset: 36)
- `value_3`: ufloatString (offset: 40)
- `value_4`: ufloatString (offset: 44)
- `value_5`: ufloatString (offset: 48)
- `value_6`: ufloatString (offset: 52)
- `value_7`: ufloatString (offset: 56)
- `value_8`: ufloatString (offset: 60)
- `value_9`: ufloatString (offset: 64)

### GIIIETHERNETSTATUS

**Fields:**

- `details`: uenumString (offset: 28)
- `reserved`: ushortString (offset: 26)
- `type`: uenumString (offset: 4)

### GIIIMEASUREMENTDATA

**Fields:**

- `ADR`: udoubleString (offset: 28)
- `AdrStd`: ufloatString (offset: 36)
- `CNO`: ufloatString (offset: 44)
- `HWChan`: ushortString (offset: 10)
- `PRN`: ushortString (offset: 4)
- `PSR`: udoubleString (offset: 16)
- `PSRstd`: ufloatString (offset: 24)
- `dopp`: ufloatString (offset: 40)
- `lockTime`: udoubleString (offset: 56)
- `sigChan`: ushortString (offset: 8)
- `svChan`: ushortString (offset: 6)

### GIIIRXCOMMANDS

**Fields:**

- `command`: ustringvariable (offset: 4)

### GIIISATPOS

**Fields:**

- `AlmAzimuth`: ufloatString (offset: 48)
- `AlmDop`: ufloatString (offset: 52)
- `AlmElevation`: ufloatString (offset: 44)
- `AlmValidity`: ushortString (offset: 22)
- `EphemAzimuth`: ufloatString (offset: 32)
- `EphemDop`: ufloatString (offset: 36)
- `EphemElevation`: ufloatString (offset: 28)
- `PRN`: ushortString (offset: 16)
- `almAzimuth`: ufloatString (offset: 48)
- `almDop`: ufloatString (offset: 52)
- `almElevation`: ufloatString (offset: 44)
- `almValidity`: ushortString (offset: 22)
- `ephAzimuth`: ufloatString (offset: 32)
- `ephDop`: ufloatString (offset: 36)
- `ephElevation`: ufloatString (offset: 28)
- `ephemValidity`: ushortString (offset: 20)
- `prn`: ushortString (offset: 16)
- `satSystem`: uenumString (offset: 0)
- `satelliteSystem`: uenumString (offset: 0)

### GIIITIMESOLUTION

**Fields:**

- `PRN`: ushortString (offset: 40)
- `clockDrift`: udoubleString (offset: 20)
- `clockOffset`: udoubleString (offset: 4)
- `ionoCorr`: ufloatString (offset: 56)
- `offsetStd`: udoubleString (offset: 12)
- `residual`: ufloatString (offset: 48)
- `sigChan`: ushortString (offset: 38)
- `svChan`: ushortString (offset: 36)
- `svPosX`: udoubleString (offset: 64)
- `svPosY`: udoubleString (offset: 72)
- `svPosZ`: udoubleString (offset: 80)
- `svclockOffset`: ufloatString (offset: 52)
- `tropoCorr`: ufloatString (offset: 60)

### GIIIVERSION

**Fields:**

- `moduleId`: ushortString (offset: 10)
- `slotId`: ushortString (offset: 8)
- `type`: uenumString (offset: 4)

### HEADING2

**Fields:**

- `extSolStat`: ucharString (offset: 45)
- `galAndBeiDouSigMask`: ucharString (offset: 46)
- `gpsAndGloSigMask`: ucharString (offset: 47)
- `hdgStdDev`: ufloatString (offset: 24)
- `heading`: ufloatString (offset: 12)
- `length`: ufloatString (offset: 8)
- `masterStnID`: udoubleString (offset: 36)
- `noOfMulti`: ucharString (offset: 43)
- `noOfObs`: ucharString (offset: 42)
- `noOfSats`: ucharString (offset: 40)
- `noOfSolSats`: ucharString (offset: 41)
- `pitch`: ufloatString (offset: 16)
- `posType`: uenumString (offset: 4)
- `ptchStdDev`: ufloatString (offset: 28)
- `roverStnID`: udoubleString (offset: 32)
- `solSource`: ucharString (offset: 44)
- `solStatus`: uenumString (offset: 0)

### HEADINGOFFSET

**Fields:**

- `headingoffsetindeg`: ufloatString (offset: 0)
- `pitchoffsetindeg`: ufloatString (offset: 4)

### HWMONITOR

**Fields:**

- `idleTime`: uhex (offset: 12)
- `reading`: ufloatString (offset: 4)

### ICOMCONFIG

**Fields:**

- `bindInterface`: uenumString (offset: 88)
- `endPoint`: ustringvariable (offset: 8)
- `port`: uenumString (offset: 0)
- `protocol`: uenumString (offset: 4)

### INSPOSX

**Fields:**

- `INS_Status`: uenumString (offset: 0)
- `extendedSolution`: uhex (offset: 48)
- `height`: udoubleString (offset: 24)
- `heightDeviation`: ufloatString (offset: 44)
- `latitude`: udoubleString (offset: 8)
- `latitudeDeviation`: ufloatString (offset: 36)
- `longitude`: udoubleString (offset: 16)
- `longitudeDeviation`: ufloatString (offset: 40)
- `positionType`: uenumString (offset: 4)
- `timeSinceUpdate`: ushortString (offset: 52)
- `undulation`: ufloatString (offset: 32)

### INSPVA

**Fields:**

- `azimuth`: udoubleString (offset: 76)
- `eastVelocity`: udoubleString (offset: 44)
- `height`: udoubleString (offset: 24)
- `latitude`: udoubleString (offset: 8)
- `longitude`: udoubleString (offset: 16)
- `northVelocity`: udoubleString (offset: 36)
- `pitch`: udoubleString (offset: 68)
- `roll`: udoubleString (offset: 60)
- `seconds`: udoubleString (offset: 4)
- `status`: uenumString (offset: 84)
- `upVelocity`: udoubleString (offset: 52)

### INSPVAX

**Fields:**

- `azimuth`: udoubleString (offset: 76)
- `azimuthDev`: ufloatString (offset: 116)
- `eastVelDev`: ufloatString (offset: 100)
- `eastVelocity`: udoubleString (offset: 44)
- `height`: udoubleString (offset: 24)
- `heightDev`: ufloatString (offset: 92)
- `latDev`: ufloatString (offset: 84)
- `latitude`: udoubleString (offset: 8)
- `longDev`: ufloatString (offset: 88)
- `longitude`: udoubleString (offset: 16)
- `northVelDev`: ufloatString (offset: 96)
- `northVelocity`: udoubleString (offset: 36)
- `pitch`: udoubleString (offset: 68)
- `pitchDev`: ufloatString (offset: 112)
- `posType`: uenumString (offset: 4)
- `roll`: udoubleString (offset: 60)
- `rollDev`: ufloatString (offset: 108)
- `status`: uenumString (offset: 0)
- `undulation`: ufloatString (offset: 32)
- `upVelDev`: ufloatString (offset: 104)
- `upVelocity`: udoubleString (offset: 52)

### INTERFACEMODE

**Fields:**

- `port`: uenumString (offset: 0)
- `responses`: uenumString (offset: 12)
- `rxType`: uenumString (offset: 4)
- `txType`: uenumString (offset: 8)

### IPCONFIG

**Fields:**

- `gateway`: ustringvariable (offset: 0)
- `interface`: uenumString (offset: 0)
- `ipAddress`: ustringvariable (offset: 8)
- `mode`: uenumString (offset: 4)
- `netmask`: ustringvariable (offset: 0)

### IPSERVICE

**Fields:**

- `ipService`: uenumString (offset: 0)
- `switch`: uenumString (offset: 4)

### ITBANDPASSFILTBANK

**Fields:**

- `frequencyStep`: ufloatString (offset: 24)
- `frequencyType`: uenumString (offset: 4)
- `maxLowerFrequencyCutOff`: ufloatString (offset: 12)
- `maxUpperFrequencyCutOff`: ufloatString (offset: 20)
- `minLowerFrequencyCutOff`: ufloatString (offset: 8)
- `minUpperFrequencyCutOff`: ufloatString (offset: 16)

### ITDETECTCONFIG

**Fields:**

- `rfpath`: uenumString (offset: 0)

### ITDETECTSTATUS

**Fields:**

- `bandwidth`: ufloatString (offset: 16)
- `centerFrequency`: ufloatString (offset: 12)
- `detectionType`: uenumString (offset: 8)
- `estimatedPower`: ufloatString (offset: 24)
- `power`: ufloatString (offset: 20)
- `rfPath`: uenumString (offset: 4)

### ITPSDDETECT

**Fields:**

- `frequencyStart`: ufloatString (offset: 4)
- `sample`: ushortString (offset: 16)
- `stepSize`: ufloatString (offset: 8)

### ITPSDFINAL

**Fields:**

- `frequencyStart`: ufloatString (offset: 4)
- `sample`: ushortString (offset: 16)
- `stepSize`: ufloatString (offset: 8)

### ITSPECTRALANALYSIS

**Fields:**

- `fftSize`: uenumString (offset: 12)
- `frequency`: uenumString (offset: 4)
- `mode`: uenumString (offset: 0)

### LBANDBEAMTABLE

**Fields:**

- `logitude`: ufloatString (offset: 28)
- `name`: ustringvariable (offset: 4)
- `reserved`: ustringvariable (offset: 12)

### LBANDTRACKSTAT

**Fields:**

- `biterrorRate`: ufloatString (offset: 60)
- `doppler`: ufloatString (offset: 24)
- `id`: ushortString (offset: 18)
- `lockTime`: ufloatString (offset: 36)
- `phaseStdDev`: ufloatString (offset: 32)
- `reserved`: ushortString (offset: 22)
- `status`: ushortString (offset: 20)

### LOGLIST

**Fields:**

- `hold`: uenumString (offset: 32)
- `message`: ushortString (offset: 8)
- `messageType`: ucharString (offset: 10)
- `offset`: udoubleString (offset: 24)
- `period`: udoubleString (offset: 16)
- `port`: uenumString (offset: 4)
- `reserved`: ucharString (offset: 11)
- `trigger`: uenumString (offset: 12)

### MARKPOS

**Fields:**

- `CRC`: uhex (offset: 72)
- `datumId`: uenumString (offset: 36)
- `differentialAge`: ufloatString (offset: 56)
- `extendedSolutionStatus`: uhex (offset: 69)
- `height`: udoubleString (offset: 24)
- `heightDeviation`: ufloatString (offset: 48)
- `idleTime`: uhex (offset: 12)
- `latitude`: udoubleString (offset: 8)
- `latitudeDeviation`: ufloatString (offset: 40)
- `longitude`: udoubleString (offset: 16)
- `longitudeDeviation`: ufloatString (offset: 44)
- `positionType`: uenumString (offset: 4)
- `satellitesTracked`: ucharString (offset: 64)
- `satellitesUsedInL1`: ucharString (offset: 66)
- `satellitesUsedInsolution`: ucharString (offset: 65)
- `satellitesWithMultiFreqCount`: ucharString (offset: 67)
- `sentenceTerminator`: uhex (offset: 4)
- `signalMaskGalBds`: uhex (offset: 70)
- `signalMaskGpsGlo`: uhex (offset: 71)
- `solutionAge`: ufloatString (offset: 60)
- `solutionStatus`: uenumString (offset: 0)
- `stationId`: ufloatString (offset: 52)
- `undulation`: ufloatString (offset: 32)

### MARKPVA

**Fields:**

- `azimuth`: udoubleString (offset: 76)
- `eastVelocity`: udoubleString (offset: 44)
- `height`: udoubleString (offset: 24)
- `latitude`: udoubleString (offset: 12)
- `longitude`: udoubleString (offset: 20)
- `northVelocity`: udoubleString (offset: 36)
- `pitch`: udoubleString (offset: 68)
- `roll`: udoubleString (offset: 60)
- `seconds`: udoubleString (offset: 4)
- `status`: uenumString (offset: 84)
- `upVelocity`: udoubleString (offset: 52)

### MODELFEATURE

**Fields:**

- `featureStatus`: uenumString (offset: 4)
- `featureType`: uenumString (offset: 8)

### NTRIPCONFIG

**Fields:**

- `bindInterface`: uenumString (offset: 0)
- `endpoint`: ustringvariable (offset: 12)
- `mountpoint`: ustringvariable (offset: 0)
- `password`: ustringvariable (offset: 0)
- `port`: uenumString (offset: 0)
- `protocol`: uenumString (offset: 8)
- `type`: uenumString (offset: 4)
- `userName`: ustringvariable (offset: 0)

### OCEANIXINFO

**Fields:**

- `subscriptionType`: uenumString (offset: 16)

### OCEANIXSTATUS

**Fields:**

- `access`: uenumString (offset: 0)
- `regionRestrictionStatus`: uenumString (offset: 8)
- `syncState`: uenumString (offset: 4)

### PORTSTATS

**Fields:**

- `port`: uenumString (offset: 4)

### POSAVE

**Fields:**

- `accuracy`: ufloatString (offset: 8)
- `maxvstd`: ufloatString (offset: 12)
- `posavetime`: ufloatString (offset: 4)
- `state`: uenumString (offset: 0)

### PSRDOP

**Fields:**

- `cutoff`: ufloatString (offset: 20)
- `gdop`: ufloatString (offset: 0)
- `hdop`: ufloatString (offset: 8)
- `htdop`: ufloatString (offset: 12)
- `pdop`: ufloatString (offset: 4)
- `tdop`: ufloatString (offset: 16)

### RTKANTENNA

**Fields:**

- `pcv`: uenumString (offset: 4)
- `posref`: uenumString (offset: 0)

### RXSTATUSEVENT

**Fields:**

- `description`: ustringvariable (offset: 12)
- `event`: uenumString (offset: 8)
- `word`: uenumString (offset: 0)

### SATEL4CONFIG

**Fields:**

- `baseType`: uenumString (offset: 16)
- `radioBehavior`: uenumString (offset: 0)

### SATEL4INFO

**Fields:**

- `fec`: uenumString (offset: 20)
- `protocol`: uenumString (offset: 0)

### SATEL9INFO

**Fields:**

- `modemMode`: uenumString (offset: 0)

### SATELDETECT

**Fields:**

- `port`: uenumString (offset: 0)

### SATELSTATUS

**Fields:**

- `state`: uenumString (offset: 0)

### SATVIS2

**Fields:**

- `almanacFlag`: uenumString (offset: 8)
- `apparentDoppler`: udoubleString (offset: 48)
- `azimuth`: udoubleString (offset: 32)
- `elevation`: udoubleString (offset: 24)
- `health`: uenumString (offset: 20)
- `satVisibility`: uenumString (offset: 4)
- `satelliteId`: uenumString (offset: 16)
- `satelliteSystem`: uenumString (offset: 0)
- `trueDoppler`: udoubleString (offset: 40)

### SBASCONTROL

**Fields:**

- `switch`: uenumString (offset: 0)
- `system`: uenumString (offset: 4)
- `testMode`: uenumString (offset: 12)

### SERIALCONFIG

**Fields:**

- `break`: uenumString (offset: 24)
- `handshake`: uenumString (offset: 20)
- `parity`: uenumString (offset: 8)
- `port`: uenumString (offset: 0)

### SETIMUORIENTATION

**Fields:**

- `switch`: uenumString (offset: 0)

### SETIMUTOANTOFFSET

**Fields:**

- `xOffset`: udoubleString (offset: 0)
- `xOffsetSD`: udoubleString (offset: 24)
- `yOffset`: udoubleString (offset: 8)
- `yOffsetSD`: udoubleString (offset: 32)
- `zOffset`: udoubleString (offset: 16)
- `zOffsetSD`: udoubleString (offset: 40)

### SETIMUTOANTOFFSET2

**Fields:**

- `xOffset`: udoubleString (offset: 0)
- `xOffsetSD`: udoubleString (offset: 24)
- `yOffset`: udoubleString (offset: 8)
- `yOffsetSD`: udoubleString (offset: 32)
- `zOffset`: udoubleString (offset: 16)
- `zOffsetSD`: udoubleString (offset: 40)

### SETINSROTATION

**Fields:**

- `rotationalOffset`: uenumString (offset: 0)
- `xRotation`: ufloatString (offset: 4)
- `xRotationSD`: ufloatString (offset: 16)
- `yRotation`: ufloatString (offset: 8)
- `yRotationSD`: ufloatString (offset: 20)
- `zRotation`: ufloatString (offset: 12)
- `zRotationSD`: ufloatString (offset: 24)

### SETINSTRANSLATION

**Fields:**

- `inputFrame`: uenumString (offset: 28)
- `insTranslation`: uenumString (offset: 0)
- `xTranslation`: ufloatString (offset: 4)
- `xTranslationSD`: ufloatString (offset: 16)
- `yTranslation`: ufloatString (offset: 8)
- `yTranslationSD`: ufloatString (offset: 20)
- `zTranslation`: ufloatString (offset: 12)
- `zTranslationSD`: ufloatString (offset: 24)

### SKCALIBRATESTATUS

**Fields:**

- `calibrationResult`: uenumString (offset: 24)
- `frontEndMode`: uenumString (offset: 20)
- `mode`: uenumString (offset: 0)
- `result`: uenumString (offset: 0)
- `signalType`: uenumString (offset: 12)
- `spoofingCalibrationMode`: uenumString (offset: 16)

### SKDETECT

**Fields:**

- `mode`: uenumString (offset: 0)

### SOFTLOADSTATUS

**Fields:**

- `status`: uenumString (offset: 0)

### TERRASTAR

**Fields:**

- `centerPointLatitude`: ufloatString (offset: 40)
- `centerPointLongitude`: ufloatString (offset: 44)
- `regionRestriction`: uenumString (offset: 36)
- `subscriptionType`: uenumString (offset: 16)

### TERRASTARSTATUS

**Fields:**

- `access`: uenumString (offset: 0)
- `syncState`: uenumString (offset: 4)

### THISANTENNAPCO

**Fields:**

- `eastOffset`: udoubleString (offset: 12)
- `frequency`: uenumString (offset: 0)
- `northOffset`: udoubleString (offset: 4)
- `upOffset`: udoubleString (offset: 20)

### THISANTENNATYPE

**Fields:**

- `antennaType`: uenumString (offset: 0)
- `radomeType`: uenumString (offset: 4)

### TIME

**Fields:**

- `clockStatus`: uenumString (offset: 0)
- `offset`: udoubleString (offset: 4)
- `offsetStd`: udoubleString (offset: 12)
- `utcDay`: ucharString (offset: 33)
- `utcHour`: ucharString (offset: 34)
- `utcMin`: ucharString (offset: 35)
- `utcMonth`: ucharString (offset: 32)
- `utcOffset`: udoubleString (offset: 20)
- `utcStatus`: uenumString (offset: 40)

### TRACTSTAT

**Fields:**

- `PRN`: ushortString (offset: 16)
- `carrierNoiseRatio`: ufloatString (offset: 36)
- `cutoff`: ufloatString (offset: 8)
- `doppler`: ufloatString (offset: 32)
- `glonassFrequency`: ushortString (offset: 18)
- `lockTime`: ufloatString (offset: 40)
- `positionType`: uenumString (offset: 4)
- `pseudoRange`: udoubleString (offset: 24)
- `pseudoRangeResidual`: ufloatString (offset: 44)
- `pseudoRangeWeight`: ufloatString (offset: 52)
- `reject`: uenumString (offset: 48)
- `solutionStatus`: uenumString (offset: 0)

### VALIDMODELS

**Fields:**

- `model`: ustringvariable (offset: 4)

### VEHICLEBODYROTATION

**Fields:**

- `xAngle`: udoubleString (offset: 0)
- `xAngleSD`: udoubleString (offset: 24)
- `yAngle`: udoubleString (offset: 8)
- `yAngleSD`: udoubleString (offset: 32)
- `zAngle`: udoubleString (offset: 16)
- `zAngleSD`: udoubleString (offset: 40)

### VERIPOSDECODERSTATUS

**Fields:**

- `comPort`: uenumString (offset: 20)
- `decoderChannel`: ushortString (offset: 26)
- `decoderSyncStatus`: ushortString (offset: 24)
- `syncState`: uenumString (offset: 12)

### VERIPOSINFO

**Fields:**

- `details`: uhex (offset: 8)
- `mode`: uenumString (offset: 4)
- `servicecode`: ucharString (offset: 12)

### VERSION

**Fields:**

- `type`: uenumString (offset: 4)

### WIFIALIGNAUTOMATION

**Fields:**

- `corrections_port`: uenumString (offset: 8)
- `headingextbopion`: uenumString (offset: 16)
- `interfacemode`: uenumString (offset: 20)
- `option`: uenumString (offset: 0)

### WIFIAPCHANNEL

### WIFIAPSETTINGS

**Fields:**

- `BSSID`: ustringvariable (offset: 20)
- `SSID`: ustringvariable (offset: 0)
- `band`: uenumString (offset: 0)
- `encryption`: uenumString (offset: 8)
- `passkey`: ustringvariable (offset: 0)
- `region`: uenumString (offset: 12)
- `security_protocol`: uenumString (offset: 4)

### WIFIMODE

**Fields:**

- `mode`: uenumString (offset: 0)

## Enumerations

### ALL_LOGS

- `category`: position
- `description`: Best available GNSS position solution

### CN

- `100`: 100
- `1000`: 1000
- `10000`: 10000
- `12`: 12.5
- `16000`: 16000
- `19200`: 19200
- `1V2_ERROR`: “数字 1V2 芯线电压”超出误差限度
- `1V2_WARNING`: “数字 1V2 芯线电压”超出警告限值
- `1V8_VOL_ERROR`: “数字 1V8 芯线电压”超出误差限度
- `1V8_VOL_WARNING`: “数字 1V8 芯线电压”超出警告限值
- `200`: 200
- `20000`: 20000
- `25`: 25.0
- `25000`: 25000
- `2D_SD`: 2d-SD
- `2d-SD`: 2d-SD
- `35000`: 35000
- `3D`: 3D
- `3V3_ERROR`: “数字芯线 3V3 电压”超出误差限度
- `3V3_WARNING`: “数字芯线 3V3 电压”超出警告限值
- *(and 1616 more)*

### CommunicationPortIdentifiers

- `0`: NOPORT
- `1`: COM1
- `10`: XCOM2
- `13`: USB1
- `14`: USB2
- `15`: USB3
- `16`: AUX
- `17`: XCOM3
- `19`: COM4
- `2`: COM2
- `20`: ETH1
- `21`: IMU
- `23`: ICOM1
- `24`: ICOM2
- `25`: ICOM3
- `26`: NCOM1
- `27`: NCOM2
- `28`: NCOM3
- `29`: ICOM4
- `3`: COM3
- *(and 25 more)*

### ConstellationErrorMessages

- `TrackedError`: Minimum of 4 satellites are required to compute position.
- `UsedError`: Minimum of 4 satellites with Good Health are required to compute position.

### ConstellationWiseSingalEnums

- `0`: L1CA
- `14`: L5Q
- `16`: L1CP
- `17`: L2CM
- `5`: L2P
- `9`: L2PCL

### ConstellationWithBands

- `BEIDOUB1`: BEIDOU B1
- `BEIDOUB1C`: BEIDOU B1C
- `BEIDOUB2`: BEIDOU B2
- `BEIDOUB2A`: BEIDOU B2A
- `BEIDOUB2B`: BEIDOU B2B
- `BEIDOUB3`: BEIDOU B3
- `GALILEOALTBOC`: GALILEO ALTBOC
- `GALILEOE1`: GALILEO E1
- `GALILEOE5A`: GALILEO E5A
- `GALILEOE5B`: GALILEO E5B
- `GALILEOE6`: GALILEO E6
- `GLONASSL1`: GLONASS L1
- `GLONASSL2`: GLONASS L2
- `GLONASSL3`: GLONASS L3
- `GPSL1`: GPS L1
- `GPSL2`: GPS L2
- `GPSL5`: GPS L5
- `LBAND`: LBAND
- `NAVICL5`: NAVIC L5
- `QZSSL1`: QZSS L1
- *(and 3 more)*

### DE

- `100`: 100
- `1000`: 1000
- `10000`: 10000
- `12`: 12,5
- `16000`: 16000
- `19200`: 19200
- `1V2_ERROR`: Digital 1V2-Kernspannung außerhalb der Fehlergrenze
- `1V2_WARNING`: Digital 1V2-Kernspannung außerhalb Warngrenze
- `1V8_VOL_ERROR`: Digital 1V8 Kernspannung außerhalb der Fehlergrenze
- `1V8_VOL_WARNING`: Digital01V8 Kernspannung außerhalb der Warngrenze
- `200`: 200
- `20000`: 20000
- `25`: 25,0
- `25000`: 25000
- `2D_SD`: 2d-SD
- `2d-SD`: 2d-SD
- `35000`: 35000
- `3D`: 3D
- `3V3_ERROR`: Digital Core 3V3-Spannung außerhalb der Fehlergrenze
- `3V3_WARNING`: Digital Core 3V3-Spannung außerhalb der Warngrenze
- *(and 1616 more)*

### EG

- `100`: 100
- `1000`: 1000
- `10000`: 10000
- `12`: 12.5
- `16000`: 16000
- `19200`: 19200
- `1V2_ERROR`: الجهد الأساسي الرقمي 1V2 خارج حد الخطأ
- `1V2_WARNING`: الجهد الأساسي الرقمي 1V2 خارج حد التحذير
- `1V8_VOL_ERROR`: الجهد الأساسي الرقمي 1V8 خارج حد الخطأ
- `1V8_VOL_WARNING`: الجهد الأساسي الرقمي 1V8 خارج حد التحذير
- `200`: 200
- `20000`: 20000
- `25`: 25.0
- `25000`: 25000
- `2D_SD`: 2d-SD
- `2d-SD`: 2d-SD
- `35000`: 35000
- `3D`: 3D
- `3V3_ERROR`: النواة الرقمية بجهد 3V3 خارج حد الخطأ
- `3V3_WARNING`: النواة الرقمية بجهد 3V3 خارج حد التحذير
- *(and 1613 more)*

### EN

- `100`: 100
- `1000`: 1000
- `10000`: 10000
- `12`: 12.5
- `16000`: 16000
- `19200`: 19200
- `1V2_ERROR`: Digital 1V2 Core Voltage outside error limit
- `1V2_WARNING`: Digital 1V2 Core Voltage outside warning limit
- `1V8_VOL_ERROR`: Digital 1V8 Core Voltage outside error limit
- `1V8_VOL_WARNING`: Digital 1V8 Core Voltage outside warning limit
- `200`: 200
- `20000`: 20000
- `25`: 25.0
- `25000`: 25000
- `2D_SD`: 2d-SD
- `2d-SD`: 2d-SD
- `35000`: 35000
- `3D`: 3D
- `3V3_ERROR`: Digital Core 3V3 Voltage outside error limit
- `3V3_WARNING`: Digital Core 3V3 Voltage outside warning limit
- *(and 1648 more)*

### ES

- `100`: 100
- `1000`: 1000
- `10000`: 10000
- `12`: 12,5
- `16000`: 16000
- `19200`: 19200
- `1V2_ERROR`: Tensión del núcleo digital 1V2 fuera del límite de error
- `1V2_WARNING`: Tensión del núcleo digital 1V2 fuera del límite de advertencia
- `1V8_VOL_ERROR`: Tensión del núcleo digital 1V8 fuera del límite de error
- `1V8_VOL_WARNING`: Tensión del núcleo digital 1V8 fuera del límite de advertencia
- `200`: 200
- `20000`: 20000
- `25`: 25,0
- `25000`: 25000
- `2D_SD`: 2d-SD
- `2d-SD`: 2d-SD
- `35000`: 35000
- `3D`: 3D
- `3V3_ERROR`: Tensión del núcleo digital 3V3 fuera del límite de error
- `3V3_WARNING`: Tensión del núcleo digital 3V3 fuera del límite de advertencia
- *(and 1616 more)*

### FR

- `100`: 100
- `1000`: 1000
- `10000`: 10000
- `12`: 12,5
- `16000`: 16000
- `19200`: 19200
- `1V2_ERROR`: Tension du noyau numérique 1V2 hors limite d’erreur
- `1V2_WARNING`: Tension du noyau numérique 1V2 hors limite d’avertissement
- `1V8_VOL_ERROR`: Tension du noyau numérique 1V8 hors limite d’erreur
- `1V8_VOL_WARNING`: Tension du noyau numérique 1V8 hors limite d’avertissement
- `200`: 200
- `20000`: 20000
- `25`: 25,0
- `25000`: 25000
- `2D_SD`: 2d-SD
- `2d-SD`: 2d-SD
- `35000`: 35000
- `3D`: 3D
- `3V3_ERROR`: Tension du noyau numérique 3V3 hors limite d’erreur
- `3V3_WARNING`: Cœur numérique 3V3 Tension hors limite d’avertissement
- *(and 1616 more)*

### FileCopyModeEnum

- `1`: MANUAL
- `2`: AUTO_ALL
- `3`: AUTO_ALL_DELETE
- `4`: AUTO_NEWEST
- `5`: AUTO_NEWEST_DELETE

### FileOperationEnum

- `1`: OPEN
- `2`: CLOSE

### FileSystemEntryTypeEnum

- `0`: NONE
- `1`: FILE
- `2`: DIR

### FileSystemOperationEnum

- `1`: OPEN
- `2`: CLOSED
- `3`: BUSY
- `4`: ERROR
- `5`: COPY
- `6`: PENDING

### FileSystemStatusConstants

- `1`: UNMOUNTED
- `2`: MOUNTED
- `3`: BUSY
- `4`: ERROR
- `5`: UNMOUNTING
- `6`: MOUNTING

### FileTransferStatusEnum

- `1`: NONE
- `2`: TRANSFERRING
- `3`: FINISHED
- `4`: ERROR
- `5`: CANCELLED

### Fn

- `bottom-left`: translate(0,-100%)
- `bottom-right`: translate(-100%,-100%)
- `top-left`: translate(0,0)
- `top-right`: translate(-100%,0)

### FormatValue

- `00`: Binary
- `01`: ASCII
- `10`: Abbr ASCII
- `11`: Reserved

### GIIIAGCCardIdEnum

- `3`: DSPC1
- `4`: DSPC2

### GIIIComponentType

- `0`: UNKNOWN
- `1`: IOMASTER
- `2`: DSPC
- `3`: RFCC
- `4`: RFDC

### GIIIEthernetDetails

- `1`: Not Connected
- `2`: 10 Mbits/Full
- `3`: 10 Mbits/Half
- `4`: 100 Mbits/Full
- `5`: 100 Mbits/Half

### GIIIEthernetInterface

- `0`: ETHA
- `1`: ETHB

### GIII_msg_triggers

- `Name`: AGCINFO
- `Triggers`: ONTIME,ONCE

### GIIIdetails

- `rxType`: GIII

### GraphTypes

- `C/NO`: cno
- `DOPPLER`: doppler
- `LOCK TIME`: lockTime
- `PSR`: psr
- `RESIDUAL`: residual

### Hr

- `property-type`: data-driven

### HwMonitorStatusReadingType

- `1`: temperature
- `15`: supplyVoltage
- `17`: voltage1V8
- `2`: antennaCurrent
- `22`: secondaryTemperature
- `23`: peripheralCoreVoltage
- `24`: secondaryAntennaCurrent
- `25`: secondaryAntennaVoltage
- `6`: digitalCoreVoltage3V3
- `7`: antennaVoltage
- `8`: digitalCoreVoltage1V2

### ITDetectStatusRFPath

- `2`: L1
- `3`: L2
- `5`: L5

### ITDetectStatusType

- `0`: SPECTRALANALYSIS
- `1`: STATISTICALANALYSIS

### LOG_STRUCTURES

- `description`: Solution status
- `name`: solutionStatus
- `type`: enum

### LogTriggerEnum

- `0`: ONNEW
- `1`: ONCHANGED
- `2`: ONTIME
- `3`: ONNEXT
- `4`: ONCE
- `5`: ONMARK
- `6`: ONALL

### MassStorageDeviceEnum

- `0`: SD
- `1`: USBSTICK
- `2`: RAMDRIVE
- `3`: DEFAULT_NO_STORAGE
- `4`: INTERNAL_FLASH

### N

- `heatmap`: histogram2d

### NComDefaultConfigObj

- `endpoint`: sid-output.com:2101
- `mountpoint`: SID08
- `operatingMode`: Receive
- `password`: MELs9tPw4
- `type`: CLIENT
- `userName`: SID

### OEM7WEBUI_Colors

- `GREEN`: #6B9B29
- `GREY`: #A9A9A9
- `RED`: #C5240F
- `YELLOW`: #EEB826

### OEMHeaderdetails

- `rxType`: OEM

### OEMdetails

- `rxType`: OEM

### OceanixSubscriptionService

- `0x2`: Oceanix H
- `0x4`: Oceanix Premium

### PT

- `100`: 100
- `1000`: 1000
- `10000`: 10000
- `12`: 12,5
- `16000`: 16000
- `19200`: 19200
- `1V2_ERROR`: Tensão 1V2 do núcleo digital fora do limite de erro
- `1V2_WARNING`: Tensão 1V2 do núcleo digital fora do limite de aviso
- `1V8_VOL_ERROR`: Tensão 1V8 do núcleo digital fora do limite de erro
- `1V8_VOL_WARNING`: Tensão 1V8 do núcleo digital fora do limite de aviso
- `200`: 200
- `20000`: 20000
- `25`: 25,0
- `25000`: 25000
- `2D_SD`: 2d-SD
- `2d-SD`: 2d-SD
- `35000`: 35000
- `3D`: 3D
- `3V3_ERROR`: Tensão 3V3 do núcleo digital fora do limite de erro
- `3V3_WARNING`: Tensão 3V3 do núcleo digital fora do limite de aviso
- *(and 1612 more)*

### PositioModeTypesDisplayStrings

- `1`: RTK BASE
- `2`: RTK ROVER
- `3`: NTRIP Server
- `4`: NTRIP Client
- `5`: PPP
- `6`: PSRDIFF BASE
- `7`: PSRDIFF ROVER
- `8`: SBAS

### PositionModeUITabSTRINGS

- `DIFFERENTIAL`: RTK
- `NTRIP`: NTRIP
- `NTRIPServer`: NTRIPServer
- `PPP`: TERRASTAR
- `PSRDIFF`: PSRDIFF
- `RTKBase`: RTKBase
- `SBAS`: SBAS

### PositionTypeDetails

- `asciiMessage`: NONE
- `description`: No position solution available

### RFcolorMap

- `L1`: rgb(105, 41, 196)
- `L2`: rgb(17, 146, 232)
- `L5`: #005d5d
- `S`: rgb(105, 41, 196)

### RU

- `100`: 100
- `1000`: 1000
- `10000`: 10000
- `12`: 12.5
- `16000`: 16000
- `19200`: 19200
- `1V2_ERROR`: Напряжение процессора 1V2  вне предела ошибок
- `1V2_WARNING`: Напряжение процессора 1V2  за пределами предупреждения
- `1V8_VOL_ERROR`: Цифровое напряжение 1V8 Core вне предела ошибок
- `1V8_VOL_WARNING`: Цифровое напряжение 1V8 Core за пределами предупреждения
- `200`: 200
- `20000`: 20000
- `25`: 25.0
- `25000`: 25000
- `2d-SD`: 2d-SD
- `35000`: 35000
- `3D`: 3D
- `3V3_ERROR`: Напряжение процессора 3V3  вне предела ошибок
- `3V3_WARNING`: Напряжение процессора 3V3  вне предела предупреждения
- `4800`: 4800
- *(and 1533 more)*

### SIDValues

- `0`: SID08
- `1`: SID09

### SolutionStatusDetails

- `asciiMessage`: SOL COMPUTED
- `description`: Solution computed
- `indicatorColor`: #6b9b29

### SwitchEnum

- `0`: DISABLE
- `1`: ENABLE

### TerrastarRegionRestriction

- `0`: NONE
- `1`: GEOGATED
- `2`: LOCAL_AREA
- `3`: NEARSHORE

### TerrastarSubscriptionType

- `0`: UNASSIGNED
- `1`: TERM
- `100`: BUBBLE
- `101`: MODEL_DENIED

### USBDetectionTypeEnum

- `1`: NONE
- `2`: USBSTICK
- `3`: PC
- `4`: ERROR

### USBModeEnum

- `0`: Device
- `1`: Host
- `2`: OTG
- `3`: Invalid
- `4`: None
- `5`: Transition

### UpdateComponentConstants

- `FIRMWARECONTENT`: Receiver Firmware
- `WEBCONTENT`: Receiver Web Content

### WifiApSettingsWifiSecurityTypeEnum

- `1`: OPEN
- `2`: WPA
- `3`: WPA2

### WifiModeEnum

- `0`: OFF
- `1`: AP
- `2`: CLIENT
- `3`: ON
- `4`: CONCURRENT

### a

- `bottom`: top

### activeFiltersAliasName

- `BEIDOU`: BDS
- `GALILEO`: GAL
- `GLONASS`: GLO
- `GPS`: GPS
- `LBAND`: LBANDLBAND
- `NAVIC`: NAVIC
- `QZSS`: QZSS

### alignStatusEnum

- `0`: SOL_COMPUTED
- `1`: INSUFFICIENT_OBS
- `13`: INTEGRITY_WARNING
- `18`: PENDING
- `19`: INVALID_FIX
- `2`: NO_CONVERGENCE
- `20`: UNAUTHORIZED
- `22`: INVALID_RATE
- `3`: SINGULARITY
- `4`: COV_TRACE
- `5`: TEST_DIST
- `6`: COLD_START
- `7`: V_H_LIMIT
- `8`: VARIANCE
- `9`: RESIDUALS

### alignmentModeEnum

- `0`: UNAIDED
- `1`: AIDED_STATIC
- `2`: AIDED_TRANSFER
- `3`: AUTOMATIC
- `4`: STATIC
- `5`: KINEMATIC

### appLayouts

- `GRIT`: grit-landing-layout
- `SM`: setupMonitor-landing-layout

### applyVBREnum

- `0`: DISABLE
- `1`: ENABLE

### chanConfigListSignalType

- `0`: GPSL1
- `1`: GPSL1L2
- `10`: GLOL1
- `105`: GALE1E5AE5BALTBOCSX
- `107`: GALE1E5AE5BALTBOCSXE6
- `11`: GALE1
- `12`: GALE5A
- `13`: GALE5B
- `14`: GALALTBOC
- `15`: BEIDOUB1
- `16`: GPSL1L2PL2C
- `17`: GPSL1L5
- `18`: SBASL1L5
- `19`: GPSL1L2PL2CL5
- `20`: GPSL1L2PL5
- `21`: GALE1E5AE5B
- `22`: GALE1E5AE5BALTBOC
- `23`: GALE1E5A
- `24`: GLOL1L2C
- `25`: GLOL1L2PL2C
- *(and 38 more)*

### colorCodes

- `blueInNAS`: #00516F
- `color`: #FFFFFF
- `configError`: #cc0b04
- `configSuccess`: #417505
- `dragTile`: url(
- `fqBoxBackground`: rgba(0, 0, 0, 0.04)
- `good`: #305703
- `hoverMask`: #ffffff
- `label`: #4a4a4a
- `lghnPaperBG`: #FCFCFC
- `lghnPlotBG`: #FCFCFC
- `lghntickColor`: #9b9b9b
- `lockTimeColor`: #00516F
- `logResponse`: RGBA(0, 0, 0, 0.87)
- `manualIcon`: ../GRIT/styles/images/Map/POI/manualPOI.svg
- `maskBG`: #d8d8d8
- `poor`: #A00214
- `poorStrengthBoxBorder`: 1px dotted rgba(245, 166, 35, 1)
- `poorfqBoxBackground`: rgba(255, 248, 238, 1)
- `selectedManualIcon`: ../GRIT/styles/images/Map/POI/dark_manualPOI.svg
- *(and 10 more)*

### compRegister

- `1335`: heading
- `1428`: IMUPort,IMUType
- `1465`: spanstatus,azimuth
- `379`: switch
- `42`: latitude,longitude,height,undulation,operatingMode,datumId,standard2D,differentialAge,stationId,heightDeviation

### componentType

- `0`: UNKNOWN
- `1`: GPSCARD
- `12`: OEM6FPGA
- `13`: GPSCARD2
- `15`: WIFI
- `18`: RADIO
- `19`: WWW_CONTENT
- `2`: CONTROLLER
- `20`: Regulatory
- `21`: OEM7FPGA
- `22`: APPLICATION
- `23`: Package
- `25`: DEFAULT_CONFIG
- `26`: WHEELSENSOR
- `27`: EMBEDDED_AUTH
- `3`: ENCLOSURE
- `7`: IMUCARD
- `8`: USERINFO
- `981073920`: DB_HEIGHTMODEL
- `981073928`: DB_WWWISO
- *(and 1 more)*

### constAlias

- `GALILEO`: GAL
- `GLONASS`: GLO

### constellationBackgroundMap

- `BEIDOU#417505`: -0px -0px
- `BEIDOU#D0021B`: -49px -0px
- `BEIDOU#F5A623`: -99px -0px
- `GALILEO#417505`: -0px -49px
- `GALILEO#D0021B`: -49px -49px
- `GALILEO#F5A623`: -99px -49px
- `GLONASS#417505`: -0px -100px
- `GLONASS#D0021B`: -49px -100px
- `GLONASS#F5A623`: -99px -100px
- `GPS#417505`: -0px -151px
- `GPS#D0021B`: -49px -151px
- `GPS#F5A623`: -99px -151px
- `Lband#417505`: -202px -146px
- `Lband#D0021B`: -288px -145px
- `Lband#F5A623`: -244px -144px
- `NAVIC#417505`: -0px -250px
- `NAVIC#D0021B`: -49px -250px
- `NAVIC#F5A623`: -99px -250px
- `QZSS#417505`: -0px -199px
- `QZSS#D0021B`: -49px -199px
- *(and 4 more)*

### constellationDomKeysToUupdateCount

- `BEIDOU`: #beidoucount
- `GALILEO`: #galileocount
- `GLONASS`: #glonasscount
- `GPS`: #gpscount
- `Lband`: #lbandcount
- `NAVIC`: #naviccount
- `QZSS`: #qzsscount
- `SBAS`: #sbascount

### constellationDomKeysToUupdateCountInCOnfig

- `BEIDOU`: #beidoucountconfig
- `GALILEO`: #galileocountconfig
- `GLONASS`: #glonasscountconfig
- `GPS`: #gpscountconfig
- `QZSS`: #qzsscountconfig
- `SBAS`: #sbascountconfig

### constellationMap

- `BEIDOU`: BDS
- `GALILEO`: GAL
- `GLONASS`: GLO
- `GPS`: GPS
- `LBAND`: LBAND
- `NAVIC`: NAVIC
- `OTHER`: OTH
- `QZSS`: QZSS
- `SBAS`: SBAS

### constellationsNameAlias

- `BEIDOU`: BDS
- `GALILEO`: GAL
- `GLONASS`: GLO

### contentDataLang

- `AUTHCODEAPPLYMESSAGE`: data-lang-authcodeapplymessage
- `COPYPROGRESSMSG`: data-lang-copyprogressmsg
- `DELETELOGCONFMSG`: data-lang-deleteconmsg
- `FILE_LOGGING_CLOSE_WARNING`: data-lang-file-logging-close
- `FRESETMESSAGE`: data-lang-fresetmessage
- `FTPCONNECTIONFAILMSG`: data-lang-ftpconnectionfailmsg
- `GRITLOGGINGINPROGRESS`: data-lang-grit-logging-inprogress
- `INVALID_AUTHORIZATION_CODE`: data-lang-auth-invalid
- `LOGFILESCLOSEWINDOWMSG`: data-lang-logfilesclosewindowmsg
- `LOGGINGINPROGRESS`: data-lang-logging-inprogress
- `MODEL_INVALID_FOR_THIS_RECEIVER`: data-lang-model-invalid
- `NASLOGGINGINPROGRESS`: data-lang-nas-logging-inprogress
- `RECEIVERRESTART_1`: data-lang-receiverrestart_1
- `RECORDINGLEAVECONFIRMATIONMESSAGE`: data-lang-terminal-recording-msg
- `STARTLOGGINGMESSAGE`: data-lang-start-logging
- `UNSAVED_POPUP_MSG`: data-lang-unsaved-popup

### correctionLogs

- `triggerType`: ONTIME

### correctionPSRDIFFLogs

- `triggerType`: ONTIME

### currentOperatingMode

- `Receive`: RECEIVE_ROVER
- `Standalone`: SINGLE_POINT
- `Transmit`: TRANSMIT_BASE

### d

- `stroke-width`: 2px

### dataLangForPosMode

- `Receive`: data-lang-receive-rover
- `Standalone`: data-lang-standalone-single-point
- `Transmit`: data-lang-transmit-base

### dataObj

- `: tempNCOMData.endpoint[0]+`: +tempNCOMData.endpoint[1],
                
- `address_mode`: DHCP
- `bindInterface`: ALL
- `comport`: COM2
- `direction`: IN
- `dns`: 0.0.0.0
- `dop`: 6000
- `endpoint`: sid-output.com:2101
- `event`: EVENT1
- `fileOperation`: OPEN
- `frequency`: LBAND
- `gateway`: 0.0.0.0
- `headingextboption`: ON
- `interfaceName`: ETHA
- `interfacemode`: NONE
- `ip_address`: 0.0.0.0
- `mode`: OFF
- `mountpoint`: SID08
- `netmask`: 255.255.255.0
- `option`: AUTO
- *(and 11 more)*

### dataObj1

- `direction`: IN2
- `event`: EVENT1

### dataObjinterfacemode

- `responses`: OFF
- `rxtype`: NOVATEL
- `txtype`: NOVATEL

### datumId

- `61`: WGS84
- `63`: USER

### defaultConfigData

- `destFolder`: /Desktop

### defaultDim

- `type`: car

### defaultDimMarPak

- `type`: largevessel

### defaultObj

- `asciiMessage`: UNKNOWN
- `description`: unkown log value
- `indicatorColor`: red

### diskActionEnum

- `0`: STOP
- `1`: OVERWRITE

### dualAntennaAlignSwitch

- `0`: DISABLE
- `1`: ENABLE

### dualAntennaMsgs

- `Category`: Measurement
- `CorrectionType`: NOVATEL
- `Name`: RANGE_1
- `Type`: SYNCH

### dummyGIIIJSON

- `4101`: type,mac,reserved,details
- `4108`: type,slotId,moduleId,psn,hwVersion,swVersion,pbcVersion,sbcVersion,fpgaVersion,compDate,compTime,fwInfoTag,pbcInfoTag,sbcInfoTag

### dummyJSON

- `101`: utcHour, utcMin, utcMS
- `1043`: sequence, satelliteSystem, numberOfSatellites, satelliteId, health, elevation, azimuth, trueDoppler
- `1071`: switch
- `1082`: headingoffsetindeg,pitchoffsetindeg
- `1146`: filestatus,filename,filesize
- `1148`: numChans,signalType
- `1194`: entries, system, satelliteID, status, signalMask
- `1205`: xOffset,yOffset,zOffset,xOffsetSD,yOffsetSD,zOffsetSD
- `1235`: status
- `1243`: mode,ipAddress,netmask,gateway
- `1244`: dnsserver,ipAddress
- `1246`: port,baud,parity,databits,stopbits,handshake,break
- `1248`: port,protocol,endPoint
- `1249`: port,type,endpoint,mountpoint,userName,password
- `1260`: mode,port
- `1289`: ipAddress
- `1296`: mode,port
- `1329`: noOfFeatures,featureStatus,featureType
- `1335`: solStatus,heading,pitch,length,hdgStdDev,ptchStdDev
- `1348`: signatureStatus,noOfAuthCodes,authCodeType,authCodeValidity,authCodeString
- *(and 71 more)*

### eAGCCalibrated

- `0`: Coarse
- `1`: Fine

### eAGCRange

- `0`: Bits 7, 6, 5
- `1`: Bits 7, 5, 4
- `2`: Bits 7, 4, 3
- `3`: Bits 7, 3, 2
- `4`: Bits 7, 2, 1
- `5`: Bits 7, 1, 0

### eBitCountOverflow

- `0`: Less than 2 bins completely filled
- `1`: 2+ Bins Completely Filled

### eBitsEmpty

- `0`: Bins contain data
- `1`: All bins are empty

### eBitsNotFull

- `0`: One of more bins filled
- `1`: All Bins Not Filled

### eGIIIActiveFlagEnum

- `0`: False
- `1`: True

### eGIIIAgcRfEnum

- `0`: L1
- `1`: L2
- `2`: L5
- `3`: S

### eGIIIBinSkew

- `0`: Not Present
- `1`: Present

### eNoiseFloorCal

- `1`: AGC
- `2`: Post Correlation

### eRailedGain

- `0`: VGA not railed
- `1`: VGA railed for 3+ seconds

### errorMessages

- `CASCADEFILTERSERROR`: CASCADEFILTERSERROR
- `GRIT_CENTERFREQOUTSIDERANGEMSG`: GRIT_CENTERFREQOUTSIDERANGEMSG
- `GRIT_CUTOFFFREQOUTSIDERANGE`: GRIT_CUTOFFFREQOUTSIDERANGE
- `NOPROGRAMMABLEFILTERS`: NOPROGRAMMABLEFILTERS

### events_data_lang_map

- `data-lang-1v2-error`: 1V2_ERROR
- `data-lang-1v2-warning`: 1V2_WARNING
- `data-lang-1v8-vol-error`: 1V8_VOL_ERROR
- `data-lang-1v8-vol-warning`: 1V8_VOL_WARNING
- `data-lang-3v3-error`: 3V3_ERROR
- `data-lang-3v3-low-error`: SUPPL_VOLTAGE_LW_ERR
- `data-lang-3v3-upper-error`: SUPPL_VOLTAGE_UPP_ERR
- `data-lang-3v3-warning`: 3V3_WARNING
- `data-lang-ant-current-error`: ANT_CURRENT_ERROR
- `data-lang-ant-current-warning`: ANT_CURRENT_WARNING
- `data-lang-ant-vol-error`: ANT_VOL_ERROR
- `data-lang-ant-vol-warning`: ANT_VOL_WARNING
- `data-lang-bds-tracking-less`: BDS_TRACKING_LESS
- `data-lang-bds-tracking-less-good`: BDS_TRACKING_LESS_GOOD
- `data-lang-com1-buffer-overrun`: COM1_BUFFER_OVERRUN
- `data-lang-com2-buffer-overrun`: COM2_BUFFER_OVERRUN
- `data-lang-ddr-temp-error`: DDR_TEMP_ERROR
- `data-lang-ddr-temp-warning`: DDR_TEMP_WARNING
- `data-lang-entered`: ENTERED_INTO
- `data-lang-error`: ERROR
- *(and 27 more)*

### exports

- `0`: NONE
- `1`: ONE
- `1024`: STENCIL_BUFFER_BIT
- `10240`: TEXTURE_MAG_FILTER
- `10241`: TEXTURE_MIN_FILTER
- `10242`: TEXTURE_WRAP_S
- `10243`: TEXTURE_WRAP_T
- `1028`: FRONT
- `1029`: BACK
- `1032`: FRONT_AND_BACK
- `10497`: REPEAT
- `10752`: POLYGON_OFFSET_UNITS
- `1280`: INVALID_ENUM
- `1281`: INVALID_VALUE
- `1282`: INVALID_OPERATION
- `1285`: OUT_OF_MEMORY
- `1286`: INVALID_FRAMEBUFFER_OPERATION
- `16384`: COLOR_BUFFER_BIT
- `2`: LINE_LOOP
- `2304`: CW
- *(and 281 more)*

### f

- `3`: LineString

### feature

- `convert-welcome`: CONVERT
- `grit-welcome`: GRIT
- `home-convert`: CONVERT
- `nas-home-menu`: HOME
- `pl-welcome`: PI
- `sm-welcome`: SM

### featureStatus

- `0`: AUTHORIZED
- `1`: UNAUTHORIZED
- `15`: STANDARD
- `2`: 0Hz
- `20`: COMMERCIAL_MEMS
- `21`: TACTICAL
- `22`: HIGH_GRADE_TACTICAL
- `23`: NAVIGATION
- `25`: SINGLE
- `26`: DUAL
- `30`: LITE
- `33`: CONSUMER_MEMS
- `37`: RADIO_TX
- `6`: 20Hz
- `8`: 100Hz
- `9`: RATE_INVALID

### featureType

- `0`: MAX_MSR_RATE
- `1`: MAX_POS_RATE
- `10`: ALIGN_HEADING
- `11`: ALIGN_RELATIVE_POS
- `12`: API
- `15`: NTRIP
- `19`: PPP
- `20`: SCINTILLATION
- `22`: INS
- `23`: IMU
- `26`: FEATURE_INTERFERENCE_MITIGATION
- `28`: ANTENNA
- `29`: GENERIC_IMU
- `3`: MEAS_OUTPUT
- `30`: INS_PLUS_PROFILES
- `31`: HEAVE
- `32`: RELATIVE_INS
- `4`: DGPS_TX
- `5`: RTK_TX
- `6`: RTK_FLOAT
- *(and 4 more)*

### formatsKeyValuePair

- `ABBREV_ASCII`: Abbreviated ASCII
- `ASCII`: ASCII
- `BINARY`: Binary
- `KML`: KML
- `RINEXv2_1`: RINEX v2.1
- `RINEXv3_01`: RINEX v3.01
- `RINEXv3_02`: RINEX v3.02
- `RINEXv3_03`: RINEX v3.03
- `RINEXv3_04`: RINEX v3.04

### getClassFromState

- `amber`: data-lang-warning
- `bad`: red-status
- `good`: green-status
- `green`: data-lang-good
- `idle`: grey-status
- `red`: data-lang-error
- `warning`: yellow-status

### gettextFromState

- `green-status`: ACTIVE
- `grey-status`: IDLE
- `red-status`: ERROR
- `yellow-status`: NODATA

### giiiComponentTypeEnums

- `0`: UNKNOWN
- `1`: IOMASTER
- `2`: DSPC
- `3`: RFCC
- `4`: RFDC

### giiiConstellationWiseSingalEnums

- `0`: L1CA
- `1`: L2P(Y)
- `14`: L1CA SBAS at L2 frequency
- `15`: L5 SBAS at L2 frequency
- `2`: L1C
- `3`: L2C
- `4`: L5
- `5`: L1CA SBAS
- `6`: L5 SBAS

### giiiOperatingMode

- `0`: Normal
- `1`: Failed

### giiiOperatingState

- `0`: OFF
- `1`: Configuration
- `2`: Operational
- `3`: Maintenance
- `4`: Boot

### giiiSatPosSystem

- `0`: GPS

### giiiSatvisConstellationMap

- `0`: GPS
- `2`: GALILEO
- `3`: NAVIC

### giiiSignalTypeEnums

- `0`: L1 C/A GPS
- `1`: L2 P(Y)
- `2`: L1 C
- `3`: L2 C
- `4`: L5 GPS
- `5`: L1 C/A SBAS
- `6`: L5 SBAS
- `64`: E1 GALILEO
- `65535`: Unknown
- `7`: L5
- `8`: S

### giiiTimeSolutionClockModel

- `0`: Not Computed
- `1`: Computed

### giii_messageSets

- `format`: Binary
- `time`: 1
- `trigger`: ONTIME

### giiitrackstatConstellationMap

- `0`: GPS
- `2`: GALILEO
- `4`: QZSS

### gpggaDataObj

- `hold`: NOHOLD
- `trigger`: ONTIME

### gpsReferenceTimeDetails

- `asciiMessage`: UNKNOWN
- `description`: Time validity is unknown
- `indicatorColor`: red

### gpsStartTime

- `G-III`: April 6, 2019 23:59:42
- `OEM`: January 6, 1980 00:00:00

### gritCompRegister

- `101`: time
- `1428`: IMUPort,IMUType
- `2065`: itkState
- `2127`: filestatus,filename,filesize
- `2143`: rfpath
- `37`: hardwareVersion
- `42`: latitude,longitude,height,satellitesTracked,satellitesUsed
- `5`: noOfLogs,port,message,messageType,trigger,period,offset
- `72`: port, rxChars, txChars
- `93`: spoofing,jamming
- `963`: idleTime

### h

- `The layout argument`: data
- `h`: v

### headers

- `User-Agent`: Mozilla/5.0 NovAtelAgent/1.0

### heaveFilterEnum

- `0`: DISABLE
- `1`: ENABLE

### i

- `X .crisp`: shape-rendering:crispEdges;
- `X .cursor-col-resize`: cursor:col-resize;
- `X .cursor-crosshair`: cursor:crosshair;
- `X .cursor-default`: cursor:default;
- `X .cursor-e-resize`: cursor:e-resize;
- `X .cursor-ew-resize`: cursor:ew-resize;
- `X .cursor-grab`: cursor:-webkit-grab;cursor:grab;
- `X .cursor-move`: cursor:move;
- `X .cursor-n-resize`: cursor:n-resize;
- `X .cursor-ne-resize`: cursor:ne-resize;
- `X .cursor-ns-resize`: cursor:ns-resize;
- `X .cursor-nw-resize`: cursor:nw-resize;
- `X .cursor-pointer`: cursor:pointer;
- `X .cursor-row-resize`: cursor:row-resize;
- `X .cursor-s-resize`: cursor:s-resize;
- `X .cursor-se-resize`: cursor:se-resize;
- `X .cursor-sw-resize`: cursor:sw-resize;
- `X .cursor-w-resize`: cursor:w-resize;
- `X .ease-bg`: -webkit-transition:background-color 0.3s ease 0s;-moz-transition:background-color 0.3s ease 0s;-ms-transition:background-color 0.3s ease 0s;-o-transition:background-color 0.3s ease 0s;transition:background-color 0.3s ease 0s;
- `X .main-svg`: position:absolute;top:0;left:0;pointer-events:none;
- *(and 34 more)*

### imuOrientation

- `1`: +X AXIS UPWARD
- `2`: -X AXIS UPWARD
- `3`: +Y AXIS UPWARD
- `4`: -Y AXIS UPWARD
- `5`: +Z AXIS UPWARD
- `6`: -Z AXIS UPWARD

### imuOrientationEnum

- `0`: AUTO
- `1`: IMU X axis is pointing UP
- `2`: IMU X axis is pointing DOWN
- `3`: IMU Y axis is pointing UP
- `4`: IMU Y axis is pointing DOWN
- `5`: IMU Z axis is pointing UP
- `6`: IMU Z axis is pointing DOWN

### imuTypeEnum

- `0`: UNKNOWN
- `1`: HG1700_AG11
- `11`: HG1700_AG58
- `12`: HG1700_AG62
- `13`: IMAR_FSAS
- `16`: KVH_COTS
- `20`: HG1930_AA99
- `26`: ISA100C
- `27`: HG1900_CA50
- `28`: HG1930_CA50
- `31`: ADIS16488
- `32`: STIM300
- `33`: KVH_1750
- `34`: ISA100
- `4`: HG1700_AG17
- `41`: EPSON_G320
- `45`: KVH-1725
- `5`: HG1900_CA29
- `50`: (7500 EVK) Bosch SMI130
- `52`: LITEF_MICROIMU
- *(and 8 more)*

### insCommandSwitchEnum

- `0`: RESET
- `1`: DISABLE
- `2`: ENABLE
- `3`: START_NO_TIME
- `4`: START_FINE_TIME
- `5`: RESTART

### insRotationEnum

- `10`: MARK4
- `11`: RBV
- `12`: RBM
- `4`: USER
- `5`: MARK1
- `6`: MARK2
- `8`: ALIGN
- `9`: MARK3

### insTranslationEnum

- `1`: ANT1
- `10`: MARK4
- `2`: ANT2
- `3`: EXTERNAL
- `4`: USER
- `5`: MARK1
- `6`: MARK2
- `7`: GIMBAL
- `9`: MARK3

### inspvaStatusEnum

- `0`: INS_INACTIVE
- `1`: INS_ALIGNING
- `10`: WAITING_AZIMUTH
- `11`: INITIALIZING_BIASES
- `12`: MOTION_DETECT
- `14`: WAITING_ALIGNMENTORIENTATION
- `2`: INS_HIGH_VARIANCE
- `3`: INS_SOLUTION_GOOD
- `6`: INS_SOLUTION_FREE
- `7`: INS_ALIGNMENT_COMPLETE
- `8`: DETERMINING_ORIENTATION
- `9`: WAITING_INITIALPOS

### inspvaxAlignment

- `0`: Incomplete
- `1`: Static
- `2`: Kinematic
- `3`: Dual Antenna
- `4`: User Command
- `5`: NVM Seed

### insvpaxConvergedFlag

- `0`: Not Converged
- `1`: Converged

### internalModuleAlias

- `GSM`: COM5
- `UHF`: USB2

### ionoCorrectionMap

- `0`: Unknown
- `1`: Klobuchar Broadcast
- `2`: SBAS Broadcast
- `3`: Multi Frequency
- `4`: PSRDiff
- `5`: NovAtel Blended

### ipConfigMode

- `1`: DHCP
- `2`: STATIC

### ipServiceEnum

- `0`: NO_PORT
- `1`: FTP_SERVER
- `2`: WEB_SERVER
- `3`: SECURE_ICOM

### ipStatusInterface

- `10`: WIFI
- `11`: WIFICLIENT
- `2`: ETHA

### itkDDCFilterType

- `0`: PASSTHROUGH
- `1`: CIC1
- `3`: CIC2
- `4`: CIC3
- `5`: HALFBAND

### itkFilterSwitch

- `0`: DISABLE
- `1`: ENABLE

### itkFrequencyType

- `0`: GPSL1
- `1`: GPSL2
- `10`: GALILEOALTBOC
- `11`: BEIDOUB1
- `12`: BEIDOUB2
- `13`: QZSSL1
- `14`: QZSSL2
- `15`: QZSSL5
- `16`: QZSSL6
- `17`: GALILEOE6
- `18`: BEIDOUB3
- `19`: GLONASSL3
- `2`: GLONASSL1
- `20`: NAVICL5
- `21`: BEIDOUB1C
- `22`: BEIDOUB2A
- `23`: BEIDOUB2B
- `3`: GLONASSL2
- `4`: Reserved
- `5`: GPSL5
- *(and 4 more)*

### itkProgFiltId

- `0`: PF0
- `1`: PF1

### itkProgFiltMode

- `0`: NOTCHFILTER
- `1`: BANDPASSFILTER
- `2`: NONE

### j

- `16`: UNSIGNED_SHORT
- `32`: FLOAT
- `8`: UNSIGNED_BYTE

### keyValuePairs

- `ALTBOC`: L5
- `B1`: L1
- `B1C`: L1
- `B2`: L2
- `B2A`: L5
- `B2B`: L2
- `BDSB3`: BDSL2
- `BEIDOU`: BDS
- `E1`: L1
- `E5A`: L5
- `E5B`: L5
- `E6`: L6
- `GALE6`: GALL2
- `GLOL3`: GLOL5
- `LBAND`: TSCL1
- `QZSSL6`: QZSSL2
- `SBAS`: SBAS

### l

- `-webkit-transform`: transform

### locationmodeToLayer

- `ISO-3`: countries
- `USA-states`: subunits
- `country names`: countries

### m

- `fill-rule`: evenodd

### map

- `TBDLine`: T
- `antenna-X-offset-dev-value`: xOffsetSD
- `antenna-X-offset-value`: xOffset
- `antenna-Y-offset-dev-value`: yOffsetSD
- `antenna-Y-offset-value`: yOffset
- `antenna-Z-offset-dev-value`: zOffsetSD
- `antenna-Z-offset-value`: zOffset
- `baseLine`: B
- `custom-ant-X-offset-value`: xOffset
- `custom-ant-Y-offset-value`: yOffset
- `custom-ant-Z-offset-value`: zOffset
- `imu-X-dev-value`: xRotationSD
- `imu-X-value`: xRotation
- `imu-Y-dev-value`: yRotationSD
- `imu-Y-value`: yRotation
- `imu-Z-dev-value`: zRotationSD
- `imu-Z-value`: zRotation
- `maxHeight`: H
- `maxLength`: L
- `maxWidth`: W
- *(and 7 more)*

### mapping

- `L5`: L3

### messageCommands

- `1`: LOG
- `1214`: ALIGNMENTMODE
- `1218`: SOFTLOADDATA
- `1243`: IPCONFIG
- `1246`: SERIALCONFIG
- `1247`: ECHO
- `1248`: ICOMCONFIG
- `1249`: NTRIPCONFIG
- `1260`: GENERATERTKCORRECTIONS
- `1296`: GENERATEDIFFCORRECTIONS
- `1349`: GENERATEALIGNCORRECTIONS
- `1411`: PROFILE
- `1428`: CONNECTIMU
- `1710`: DHCPCONFIG
- `1719`: TERRASTARINFO
- `1733`: ASSIGNLBANDBEAM
- `1735`: ELEVATIONCUTOFF
- `1761`: DUALANTENNAALIGN
- `1795`: AUTOSURVEY
- `1920`: SETINSTRANSLATION
- *(and 25 more)*

### messageIds

- `Category`: Position
- `CorrectionType`: NOVATEL
- `Name`: CLOCKSTEERING
- `Type`: ASYNCH

### messageNumbers

- `1`: gnssHardwareVersion
- `3`: gnssSerialNumber
- `4`: gnssModelNumber
- `5`: gnssSoftwareVersion
- `6`: gnssBootVersion

### messagePeriods

- `Name`: HWMONITOR
- `Period`: 10

### messageSets

- `format`: Binary
- `time`: 1
- `trigger`: ONTIME

### messageTriggers

- `Name`: MARK1PVA
- `Trigger`: ONNEW

### modemMode

- `2`: P2MP_MASTER
- `3`: P2MP_SLAVE
- `8`: P2MP_RX_SLAVE

### n

- `2`: mat2
- `3`: mat3
- `4`: mat4

### nmeaBeiDouTalkeroption

- `0`: GB
- `1`: BD

### nmeaFormatFields

- `0`: GGA_LATITUDE
- `1`: GGA_LONGITUDE
- `10`: GGALONG_LATITUDE
- `11`: GGALONG_LONGITUDE
- `12`: GGALONG_ALTITUDE
- `13`: GGALONG_UNDULATION
- `2`: GGA_ALTITUDE
- `3`: GGA_UNDULATION

### nmeaTalkeroption

- `0`: GP
- `1`: AUTO

### ntripConfig

- `type`: DISABLED

### o

- `20`: Fruitbat
- `21`: Anchovy
- `new`: replace
- `xlink:xlink:show`: _blank

### observationStatus

- `0`: GOOD
- `1`: BADHEALTH
- `10`: INVALIDIODE
- `100`: BAD_INTEGRITY
- `101`: LOSSOFLOCK
- `102`: NOAMBIGUITY
- `11`: LOCKEDOUT
- `12`: LOWPOWER
- `13`: OBSL2
- `15`: UNKNOWN
- `16`: NOIONOCORR
- `17`: NOTUSED
- `18`: OBSL1
- `19`: OBSE1
- `2`: OLDEPHEMERIS
- `20`: OBSL5
- `21`: OBSE5
- `22`: OBSB2
- `23`: OBSB1
- `24`: OBSB3
- *(and 7 more)*

### opts

- `class`: btn-default

### payload

- `status`: success

### poiIcons

- `manual`: M9.99984 0.666504C4.85317 0.666504 0.666504 4.85317 0.666504 9.99984C0.666504 16.9998 9.99984 27.3332 9.99984 27.3332C9.99984 27.3332 19.3332 16.9998 19.3332 9.99984C19.3332 4.85317 15.1465 0.666504 9.99984 0.666504ZM15.3332 11.3332H11.3332V15.3332H8.6665V11.3332H4.6665V8.6665H8.6665V4.6665H11.3332V8.6665H15.3332V11.3332Z

### portsMap

- `0`: NO_PORTS
- `1`: COM1_ALL
- `10`: XCOM2_ALL
- `10144`: ICOM6
- `10172`: ICOM6_28
- `10173`: ICOM6_29
- `10174`: ICOM6_30
- `10400`: ICOM7
- `10428`: ICOM7_28
- `10429`: ICOM7_29
- `10430`: ICOM7_30
- `124`: COM3_28
- `125`: COM3_29
- `126`: COM3_30
- `13`: USB1_ALL
- `14`: USB2_ALL
- `1440`: USB1
- `1468`: USB1_28
- `1469`: USB1_29
- `1470`: USB1_30
- *(and 87 more)*

### portsMapForLoglist

- `0`: NO_PORTS
- `1`: COM1_ALL
- `10`: XCOM2_ALL
- `10173`: ICOM6_29
- `10174`: ICOM6_30
- `10429`: ICOM7_29
- `10430`: ICOM7_30
- `125`: COM3_29
- `13`: USB1_ALL
- `14`: USB2_ALL
- `1469`: USB1_29
- `15`: USB3_ALL
- `16`: AUX_ALL
- `17`: XCOM3_ALL
- `1725`: USB2_29
- `19`: COM4_ALL
- `192`: THISPORT
- `1981`: USB3_29
- `2`: COM2_ALL
- `20`: ETH1_ALL
- *(and 45 more)*

### posaveStatus

- `0`: OFF
- `1`: INPROGRESS
- `2`: COMPLETE

### positionType

- `0`: NONE
- `1`: FIXEDPOS
- `16`: SINGLE
- `17`: PSRDIFF
- `18`: WAAS
- `19`: PROPAGATED
- `2`: FIXEDHEIGHT
- `32`: L1_FLOAT
- `33`: IONOFREE_FLOAT
- `34`: NARROW_FLOAT
- `4`: FLOATCONV
- `48`: L1_INT
- `49`: WIDE_INT
- `5`: WIDELANE
- `50`: NARROW_INT
- `51`: RTK_DIRECT_INS
- `52`: INS_SBAS
- `53`: INS_PSRSP
- `54`: INS_PSRDIFF
- `55`: INS_RTKFLOAT
- *(and 14 more)*

### projNames

- `4`: eckert4
- `7`: kavrayskiy7
- `albers usa`: albersUsa
- `azimuthal equal area`: azimuthalEqualArea
- `azimuthal equidistant`: azimuthalEquidistant
- `conic conformal`: conicConformal
- `conic equal area`: conicEqualArea
- `conic equidistant`: conicEquidistant
- `natural earth`: naturalEarth
- `transverse mercator`: transverseMercator
- `winkel tripel`: winkel3

### radioBehaviourEnum

- `0`: RX
- `1`: TX

### ragStatuses

- `ANTENNA_AMBER`: Antenna Voltage warning level reached
- `ANTENNA_RED`: Antenna Voltage critical limit reached
- `CPUUSAGE_AMBER`: CPU usage is high
- `CPUUSAGE_RED`: CPU usage is critical
- `DETERMINING_ORIENTATION`: Determining Orientation <br \> INS is determining the IMU axis aligned with gravity.
- `INITIALIZING_BIASES`: Initializing Biases <br \> The INS filter is estimating initial biases during the first 10 seconds of stationary data.
- `INSUFFICIENT_OBS`: Insufficient GNSS satellites to calculate position
- `INS_ALIGNING`: INS Aligning <br \> INS is in alignment mode.
- `INS_ALIGNMENT_COMPLETE`: INS Alignment Complete <br \> The INS filter is in navigation mode, but not enough vehicle dynamics have been experienced for the system to be within specifications.
- `INS_HIGH_VARIANCE`: High INS Variance <br \> The INS solution is in navigation mode but the azimuth solution uncertainty has exceeded the threshold. The solution is still valid but you should monitor the solution uncertainty.
- `INS_INACTIVE`: INS Inactive <br \> The alignment routine has not been started
- `INS_SOLUTION_FREE`: INS Solution Free <br \> The INS filter is in navigation mode and the GNSS solution is suspected to be in error. The inertial filter has rejected the GNSS position and is waiting for the solution quality to improve.
- `INTEGRITY_WARNING`: Large residuals causing unreliable position
- `INVALID_FIX`: The configured fixed position is not valid
- `MOTION_DETECT`: Motion Detect <br \> The INS filter has not completely aligned, but has detected motion.
- `NARROW_FLOAT`: RTK solution with unresolved carrier phase ambiguities
- `NO_CONVERGENCE`: PPP solution failed to converge
- `PPP_INTERMEDIATE_STATE`: PPP solution in use, but is converging
- `PSRDIFF`: Solution using pseudorange differential corrections
- `STORAGEUSAGE_AMBER`: Storage usage is high
- *(and 20 more)*

### rejectCodeColorEnums

- `0`: #417505
- `1`: #F5A623
- `10`: #F5A623
- `100`: #F5A623
- `101`: #F5A623
- `102`: #F5A623
- `11`: #F5A623
- `12`: #F5A623
- `13`: #417505
- `15`: #F5A623
- `16`: #F5A623
- `17`: #F5A623
- `18`: #417505
- `19`: #417505
- `2`: #F5A623
- `20`: #417505
- `21`: #417505
- `22`: #417505
- `23`: #417505
- `24`: #417505
- *(and 9 more)*

### replacements

- `GAL`: GALILEO
- `GLO`: GLONASS
- `LBANDLBAND`: LBAND

### reqLogs

- `0`: LOG VERSION
- `1`: LOG VALIDMODELS
- `10`: LOG USERANTENNA
- `11`: LOG TERRASTARAUTOCHANCONFIG
- `12`: LOG SATEL4INFO
- `13`: LOG SATEL9INFO
- `14`: LOG CLOCKCALIBRATE
- `2`: LOG RXCONFIG
- `3`: LOG CHANCONFIG
- `4`: LOG PROFILEINFO
- `5`: LOG SETUTCLEAPSECONDS
- `6`: LOG SETBASEWEEK
- `7`: LOG NVMUSERDATA
- `8`: LOG TERRASTARINFO
- `9`: LOG SAVEDSURVEYPOSITIONS

### responses

- `cool`: Great! What else can I analyze for you?
- `good`: Glad to help! What
- `got it`: Perfect! Feel free to ask more questions.
- `great`: Excellent! Let me know if you need more analysis.
- `hello`: Hi! I can help you analyze GNSS receiver logs and answer questions about NovAtel OEM7 documentation.
- `hey`: Hey! Ready to analyze your receiver logs. What would you like to know?
- `hi`: Hello! I
- `nice`: Thanks! Anything else you
- `ok`: Great! What would you like to analyze next?
- `okay`: Sounds good! Anything else I can help with?
- `perfect`: Wonderful! Let me know if you need anything else.
- `thank you`: Happy to help! Feel free to ask more questions.
- `thanks`: You
- `yes`: Understood. What would you like to do?

### routeStyle

- `rgba(0, 81, 111,0.87)`: rgba(39, 160, 191,0.87)

### rsStatusEventTypeEnum

- `0`: CLEAR
- `1`: SET

### rsStatusEventWordEnum

- `0`: ERROR
- `1`: STATUS
- `2`: AUX1
- `3`: AUX2
- `4`: AUX3
- `5`: AUX4

### rxStatusPortsMap

- `10`: ICOM3
- `11`: ICOM2
- `12`: ICOM1
- `21`: USB3
- `22`: USB2
- `23`: USB1
- `7`: NCOM3
- `8`: NCOM2
- `9`: NCOM1

### s

- `Content-Type`: text/plain
- `shape-rendering`: crispEdges

### satValDescriptionJson

- `0`: Good
- `1`: Bad Health
- `10`: Invalid Iode
- `100`: Bad Integrity
- `101`: Lock Broken
- `102`: No RTK Ambiguity
- `11`: Locked Out
- `12`: Low Power
- `13`: L2 Observation
- `15`: Unknown
- `16`: No Ionospheric Corrections
- `17`: Not Used In Solution
- `18`: L1 Observation
- `19`: E1 Observation
- `2`: Old Ephemeris
- `20`: L5 Observation
- `21`: E5 Observation
- `22`: B2 Observation
- `23`: B1 Observation
- `24`: B3 Observation
- *(and 7 more)*

### satel4BaseTypeEnum

- `0`: PACCREST
- `4`: TRIMBLE
- `9`: NONE

### satel4CompatibilityModeEnum

- `1`: Pacific Crest Compatible, GMSK, 4800 / 12.5, FEC on
- `10`: Satel 3AS 4FSK, 9600, FEC off
- `11`: Pacific Crest Compatible, GMSK, 9600 / 25.0, FEC on
- `12`: Pacific Crest Compatible, GMSK, 9600, FEC off *
- `13`: Pacific Crest Compatible, 4FSK, 19200 / 25.0, FEC on
- `14`: Pacific Crest Compatible 4FSK, , 19200, FEC off *
- `15`: Pacific Crest FST Compatible, 4FSK, 19200 / 25.0, FEC on
- `16`: Pacific Crest FST Compatible 4FSK, 19200, FEC off *
- `17`: Trimtalk Compatible, GMSK, 9600 / 25.0
- `18`: Trimtalk Compatible,  GMSK, 16000 **
- `19`: Satel 3AS, 4FSK, 19200 / 25.0, FEC on
- `2`: Pacific Crest Compatible, GMSK, 4800, FEC off *
- `20`: Satel 3AS, 4FSK, 19200 / 25.0, FEC off
- `3`: Pacific Crest Compatible, 4FSK, 9600 / 12.5, FEC on
- `4`: Pacific Crest Compatible, 4FSK, 9600, FEC off *
- `5`: Pacific Crest FST Compatible, 4FSK, 9600 / 12.5, FEC on
- `6`: Pacific Crest FST Compatible, 4FSK, 9600, FEC off *
- `7`: Trimtalk Compatible, GMSK, 4800 / 12.5
- `8`: Trimtalk Compatible, GMSK, 8000 **
- `9`: Satel 3AS, 4FSK, 9600 / 12.5, FEC on

### satel4ConfigCompatibilityEnum

- `1`: Pacific Crest/GMSK/4800/12.5/ON
- `10`: Satel 3AS/4FSK/9600/12.5/OFF
- `11`: Pacific Crest/GMSK/9600/25.0/ON
- `12`: Pacific Crest/GMSK/9600/25.0/OFF
- `13`: Pacific Crest/4FSK/19200/25.0/ON
- `14`: Pacific Crest/4FSK/19200/25.0/OFF
- `15`: Pacific Crest FST/4FSK/19200/25.0/ON
- `16`: Pacific Crest FST/4FSK/19200/25.0/OFF
- `17`: Trimtalk/GMSK/9600/25.0/*
- `18`: Trimtalk/GMSK/16000/*/*
- `19`: Satel 3AS/4FSK/19200/25.0/ON
- `2`: Pacific Crest/GMSK/4800/12.5/OFF
- `20`: Satel 3AS/4FSK/19200/25.0/OFF
- `3`: Pacific Crest/4FSK/9600/12.5/ON
- `4`: Pacific Crest/4FSK/9600/12.5/OFF
- `5`: Pacific Crest FST/4FSK/9600/12.5/ON
- `6`: Pacific Crest FST/4FSK/9600/12.5/OFF
- `7`: Trimtalk/GMSK/4800/12.5/*
- `8`: Trimtalk/GMSK/8000/*/*
- `9`: Satel 3AS/4FSK/9600/12.5/ON

### satel4ProtocolEnum

- `0`: Satelline-3AS
- `1`: PacCrest-4FSK
- `2`: PacCrest-GMSK
- `3`: Trimtalk450s (PacCrest transmitter)
- `4`: Trimtalk450s (Trimble transmitter)
- `5`: PacCrest-FST

### satel900Protocol

- `LEICA`: Freewave Leica
- `NOVARIANT`: Freewave Novariant

### satelDetectPortEnum

- `1`: COM1
- `2`: COM2
- `3`: COM3

### satelStatusErrorEnum

- `0`: NONE
- `1`: COMMAND_FAILED
- `2`: TIMEOUT

### satelStatusStateEnum

- `0`: OFF
- `1`: UNDETECTED
- `2`: DETECTING
- `3`: READY
- `4`: BUSY
- `5`: ERROR

### satelliteNameFromTrackerID

- `BD`: BEIDOU
- `GA`: GALILEO
- `GP`: GPS

### satvisConstellationMap

- `0`: GPS
- `1`: GLONASS
- `2`: SBAS
- `5`: GALILEO
- `6`: BEIDOU
- `7`: QZSS
- `9`: NAVIC

### serialPortEnum

- `1`: COM1
- `19`: COM4
- `2`: COM2
- `3`: COM3
- `31`: COM5
- `32`: COM6
- `33`: BT1
- `34`: COM7
- `35`: COM8
- `36`: COM9
- `37`: COM10
- `7`: SPI

### setIMUeventDirectionEnum

- `1`: IN
- `2`: OUT
- `3`: IN2

### setIMUeventEnum

- `1`: OFF
- `2`: DEFAULT
- `3`: EVENT1
- `4`: EVENT2
- `5`: EVENT3
- `6`: EVENT4

### signalColors

- `1`: sigType1
- `2`: sigType2
- `3`: sigType3
- `4`: sigType4
- `5`: sigType5

### signalTypeDesc

- `BEIDOUB1`: B1I
- `BEIDOUB1B1C`: B1I,B1C
- `BEIDOUB1B1CB2`: B1I,B1C,B2I/B2a
- `BEIDOUB1B1CB2B`: B1I,B1C,B2b
- `BEIDOUB1B1CB2B2B`: B1I,B1C,B2I/B2a,B2b
- `BEIDOUB1B1CB2B2BB3`: B1I,B1C,B2I/B2a,B2b,B3I
- `BEIDOUB1B1CB2B3`: B1I,B1C,B2I/B2a,B3I
- `BEIDOUB1B1CB2IB2B`: B1I,B1C,B2I,B2b
- `BEIDOUB1B1CB2IB2BB3`: B1I,B1C,B2I,B2b,B3I
- `BEIDOUB1B2`: B1I,B2I/B2a
- `BEIDOUB1B2B`: B1I,B2b
- `BEIDOUB1B2B2B`: B1I,B2I/B2a,B2b
- `BEIDOUB1B2B2BB3`: B1I,B2I/B2a,B2b,B3I
- `BEIDOUB1B2B3`: B1I,B2I/B2a,B3I
- `BEIDOUB1B2IB2B`: B1I,B2I,B2b
- `BEIDOUB1B2IB2BB3`: B1I,B2I,B2b,B3I
- `BEIDOUB1B3`: B1I,B3I
- `BEIDOUB1C`: B1C
- `BEIDOUB3`: B3I
- `GALALTBOC`: ALTBOCQ
- *(and 39 more)*

### signalTypesMap

- `GPSL1`: L1
- `GPSL1L2`: L1,L2
- `GPSL1L2AUTO`: L1,L2
- `GPSL1L2C`: L1,L2
- `GPSL1L2PL2C`: L1,L2
- `GPSL1L2PL2CL1C`: L1,L2
- `GPSL1L2PL2CL5`: L1,L2,L5
- `GPSL1L2PL2CL5L1C`: L1,L2,L5
- `GPSL1L2PL5`: L1,L2,L5
- `GPSL1L5`: L1,L5
- `GPSL5`: L5

### signal_type_map

- `0`: GPSL1
- `1`: GPSL1L2
- `10`: GLOL1
- `11`: GALE1
- `12`: GALE5A
- `13`: GALE5B
- `14`: GALALTBOC
- `15`: BEIDOUB1
- `16`: GPSL1L2PL2C
- `17`: GPSL1L5
- `18`: SBASL1L5
- `19`: GPSL1L2PL2CL5
- `20`: GPSL1L2PL5
- `21`: GALE1E5AE5B
- `22`: GALE1E5AE5BALTBOC
- `23`: GALE1E5A
- `24`: GLOL1L2C
- `25`: GLOL1L2PL2C
- `26`: QZSSL1CA
- `27`: QZSSL1CAL2C
- *(and 35 more)*

### sixthCharObj

- `0`: 0 Hz
- `1`: 1 Hz
- `5`: 5 Hz

### skCalibrateModeEnum

- `0`: ALL
- `1`: REMAINING

### skCalibrateStatusModeEnum

- `0`: PASS
- `1`: FAIL
- `2`: INPROGRESS
- `3`: NONE

### skDetectModeEnum

- `0`: DISABLE
- `1`: ENABLE

### softloadStatusType

- `1`: NOT_STARTED
- `10`: COPIED_SIGNATURE_AUTH
- `11`: WROTE_TRANSACTION_TABLE
- `16`: ERROR
- `17`: RESET_ERROR
- `18`: BAD_SRECORD
- `19`: BAD_PLATFORM
- `2`: READY_FOR_SETUP
- `20`: BAD_MODULE
- `21`: BAD_AUTHCODE
- `22`: NOT_READY_FOR_SETUP
- `23`: NO_MODULE
- `24`: NO_PLATFORM
- `25`: NOT_READY_FOR_DATA
- `26`: MODULE_MISMATCH
- `27`: OUT_OF_MEMORY
- `28`: DATA_OVERLAP
- `29`: BAD_IMAGE_CRC
- `3`: READY_FOR_DATA
- `30`: IMAGE_OVERSIZE
- *(and 11 more)*

### solutionStatus

- `0`: SOL_COMPUTED
- `1`: INSUFFICIENT_OBS
- `13`: INTEGRITY_WARNING
- `18`: PENDING
- `19`: INVALID_FIX
- `2`: NO_CONVERGENCE
- `20`: UNAUTHORIZED
- `22`: INVALID_RATE
- `3`: SINGULARITY
- `4`: COV_TRACE
- `5`: TEST_DIST
- `6`: COLD_START
- `7`: V_H_LIMIT
- `8`: VARIANCE
- `9`: RESIDUALS

### spanStatusStringMap

- `DETERMINING_ORIENTATION`: Determining Orientation
- `INITIALIZING_BIASES`: Initializing Biases
- `INS_ALIGNING`: INS Aligning
- `INS_ALIGNMENT_COMPLETE`: INS Alignment Complete
- `INS_HIGH_VARIANCE`: High INS Variance
- `INS_INACTIVE`: INS Inactive
- `INS_SOLUTION_FREE`: INS Solution Free
- `INS_SOLUTION_GOOD`: INS Solution Good
- `MOTION_DETECT`: Motion Detect
- `WAITING_AZIMUTH`: Waiting For Azimuth
- `WAITING_INITIALPOS`: Waiting for Initial Pos

### style

- `rgba(0, 171, 200, 0.3)`: rgba(0, 81, 111, 0.1)
- `rgba(0, 81, 111, 0.1)`: rgba(0, 171, 200, 0.3)

### t

- `1`: ),q3:a(t,
- `3`: ):a(t,

### tabEnum

- `1`: imuSetup
- `2`: rotationalOffsets
- `3`: antennaOffsets

### textAndDataLangMap

- `AGC_PULSE_WIDTH_ABOVE_900`: data-lang-pulse-width-above
- `AGC_PULSE_WITH_BELOW_100`: data-lang-pulse-width-below
- `BINS_EMPTY`: data-lang-bins-empty
- `BINS_NOT_FULL`: data-lang-bins-not-empty
- `BIN_SKEW_1`: data-lang-bin-skew
- `RAILED_GAIN_1`: data-lang-railed-gain

### textStyle

- `18px OpenSans-Bold`: 18px OpenSans-Regular
- `bold 14px OpenSans-Regular`: 14px OpenSans-Regular
- `rgba(0,81,111,1.5)`: rgba(0,81,111,0.9)

### tn

- `:[22,[20,25,2,-7]],0:[20,[9,21,6,20,4,17,3,12,3,9,4,4,6,1,9,0,11,0,14,1,16,4,17,9,17,12,16,17,14,20,11,21,9,21]],1:[20,[6,17,8,18,11,21,11,0]],2:[20,[4,16,4,17,5,19,6,20,8,21,12,21,14,20,15,19,16,17,16,15,15,13,13,10,3,0,17,0]],3:[20,[5,21,16,21,10,13,13,13,15,12,16,11,17,8,17,6,16,3,14,1,11,0,8,0,5,1,4,2,3,4]],4:[20,[13,21,3,7,18,7,-1,-1,13,21,13,0]],5:[20,[15,21,5,21,4,12,5,13,8,14,11,14,14,13,16,11,17,8,17,6,16,3,14,1,11,0,8,0,5,1,4,2,3,4]],6:[20,[16,18,15,20,12,21,10,21,7,20,5,17,4,12,4,7,5,3,7,1,10,0,11,0,14,1,16,3,17,6,17,7,16,10,14,12,11,13,10,13,7,12,5,10,4,7]],7:[20,[17,21,7,0,-1,-1,3,21,17,21]],8:[20,[8,21,5,20,4,18,4,16,5,14,7,13,11,12,14,11,16,9,17,7,17,4,16,2,15,1,12,0,8,0,5,1,4,2,3,4,3,7,4,9,6,11,9,12,13,13,15,14,16,16,16,18,15,20,12,21,8,21]],9:[20,[16,14,15,11,13,9,10,8,9,8,6,9,4,11,3,14,3,15,4,18,6,20,9,21,10,21,13,20,15,18,16,14,16,9,15,4,13,1,10,0,8,0,5,1,4,3]],`: :[10,[5,14,4,13,5,12,6,13,5,14,-1,-1,5,2,4,1,5,0,6,1,5,2]],

### toReplace

- `LBAND`: LBand

### topics_map

- `alignment`: alignment setup
- `antenna`: antenna setup
- `base station`: base station setup
- `beidou`: BeiDou setup
- `bestpos`: BESTPOS message
- `correction`: correction services
- `ethernet`: Ethernet setup
- `event`: event markers
- `galileo`: Galileo setup
- `glonass`: GLONASS setup
- `gnss`: GNSS configuration
- `gps`: GPS setup
- `heading`: heading configuration
- `imu`: IMU setup
- `log`: logging configuration
- `ntrip`: NTRIP configuration
- `port`: port configuration
- `ppp`: PPP configuration
- `pps`: PPS output
- `rover`: rover configuration
- *(and 9 more)*

### trackstatConstellationMap

- `0`: GPS
- `1`: GLONASS
- `2`: SBAS
- `3`: GALILEO
- `4`: BEIDOU
- `5`: QZSS
- `6`: NAVIC
- `7`: OTHER

### trackstatSingalEnums

- `0`: L1CA
- `14`: L5Q
- `16`: L1CP
- `17`: L2CM
- `5`: L2P
- `9`: L2PCL

### unitsMap

- `default`:  m
- `russian-lang`:  M

### unlogDataObj

- `port`: THISPORT_30

### veriposInfoModeEnum

- `0`: UNASSIGNED
- `100`: BUBBLE
- `101`: MODEL_DENIED
- `7`: NCC_CONTROLLED
- `8`: NO_DISABLE

### wifiAlignAutomationoption

- `0`: DISABLE
- `1`: ENABLE

### wifiStatusEnum

- `0`: Startup
- `1`: Off
- `10`: Upgrading Firmware
- `11`: Upgrading Firmware 10
- `12`: Upgrading Firmware 20
- `13`: Upgrading Firmware 30
- `14`: Upgrading Firmware 40
- `15`: Upgrading Firmware 50
- `16`: Upgrading Firmware 60
- `17`: Upgrading Firmware 70
- `18`: Upgrading Firmware 80
- `19`: Upgrading Firmware 90
- `2`: On
- `20`: Upgrading Firmware Complete
- `21`: Error
- `22`: Configuring Concurrent
- `23`: Concurrent Operational
- `24`: Connecting To AP
- `25`: Connected To AP
- `26`: Connection Failure
- *(and 15 more)*

### xs

- `!`: \ufe15
- `#`: \uff03
- `%`: \uff05
- `&`: \uff06
- `(`: \ufe35
- `)`: \ufe36
- `*`: \uff0a
- `+`: \uff0b
- `,`: \ufe10
- `-`: \ufe32
- `.`: \u30fb
- `/`: \uff0f
- `:`: \ufe13
- `;`: \ufe14
- `<`: \ufe3f
- `=`: \uff1d
- `>`: \ufe40
- `?`: \ufe16
- `@`: \uff20
- `[`: \ufe47
- *(and 6 more)*

## Bit Positions

### Bit 5

- antenna not powered/open/short)

### Bit 10

- "Spoofing detected",  # KEY BIT

## Field Names

- `ADR` (udoubleString): Used in GIIIMEASUREMENTDATA, GIIIMEASUREMENTDATA
- `AdrStd` (ufloatString): Used in GIIIMEASUREMENTDATA, GIIIMEASUREMENTDATA
- `AlmAzimuth` (ufloatString): Used in GIIISATPOS, GIIISATPOS
- `AlmDop` (ufloatString): Used in GIIISATPOS, GIIISATPOS
- `AlmElevation` (ufloatString): Used in GIIISATPOS, GIIISATPOS
- `AlmValidity` (ushortString): Used in GIIISATPOS, GIIISATPOS
- `BSSID` (ustringvariable): Used in WIFIAPSETTINGS, WIFIAPSETTINGS
- `CNO` (ufloatString): Used in GIIIMEASUREMENTDATA, GIIIMEASUREMENTDATA
- `CRC` (uhex): Used in BESTPOS, MARKPOS, BESTPOS, MARKPOS
- `EphemAzimuth` (ufloatString): Used in GIIISATPOS, GIIISATPOS
- `EphemDop` (ufloatString): Used in GIIISATPOS, GIIISATPOS
- `EphemElevation` (ufloatString): Used in GIIISATPOS, GIIISATPOS
- `HWChan` (ushortString): Used in GIIIMEASUREMENTDATA, GIIIMEASUREMENTDATA
- `IMUPort` (uenumString): Used in CONNECTIMU, CONNECTIMU
- `IMUType` (uenumString): Used in CONNECTIMU, CONNECTIMU
- `INS_Status` (uenumString): Used in INSPOSX, INSPOSX
- `PRN` (ushortString): Used in TRACTSTAT, GIIITIMESOLUTION, GIIIMEASUREMENTDATA, GIIISATPOS, TRACTSTAT, and 3 more
- `PSR` (udoubleString): Used in GIIIMEASUREMENTDATA, GIIIMEASUREMENTDATA
- `PSRstd` (ufloatString): Used in GIIIMEASUREMENTDATA, GIIIMEASUREMENTDATA
- `SSID` (ustringvariable): Used in WIFIAPSETTINGS, WIFIAPSETTINGS
- `SignalMask` (uhex): Used in BESTSATS, BESTSATS
- `access` (uenumString): Used in OCEANIXSTATUS, TERRASTARSTATUS, OCEANIXSTATUS, TERRASTARSTATUS
- `accuracy` (ufloatString): Used in AUTOSURVEY, POSAVE, AUTOSURVEY, POSAVE
- `almAzimuth` (ufloatString): Used in GIIISATPOS, GIIISATPOS
- `almDop` (ufloatString): Used in GIIISATPOS, GIIISATPOS
- `almElevation` (ufloatString): Used in GIIISATPOS, GIIISATPOS
- `almValidity` (ushortString): Used in GIIISATPOS, GIIISATPOS
- `almanacFlag` (uenumString): Used in SATVIS2, SATVIS2
- `antennaType` (uenumString): Used in THISANTENNATYPE, BASEANTENNATYPE, THISANTENNATYPE, BASEANTENNATYPE
- `apparentDoppler` (udoubleString): Used in SATVIS2, SATVIS2
- `authCodeString` (ustringvariable): Used in AUTHCODES, AUTHCODES
- `authCodeType` (uenumString): Used in AUTHCODES, AUTHCODES
- `azimuth` (udoubleString): Used in SATVIS2, INSPVA, INSPVAX, MARKPVA, SATVIS2, and 3 more
- `azimuthDev` (ufloatString): Used in INSPVAX, INSPVAX
- `band` (uenumString): Used in WIFIAPSETTINGS, WIFIAPSETTINGS
- `bandwidth` (ufloatString): Used in ITDETECTSTATUS, ITDETECTSTATUS
- `baseType` (uenumString): Used in SATEL4CONFIG, SATEL4CONFIG
- `bindInterface` (uenumString): Used in NTRIPCONFIG, ICOMCONFIG, NTRIPCONFIG, ICOMCONFIG
- `biterrorRate` (ufloatString): Used in LBANDTRACKSTAT, LBANDTRACKSTAT
- `break` (uenumString): Used in SERIALCONFIG, SERIALCONFIG
- `calibrationResult` (uenumString): Used in SKCALIBRATESTATUS, SKCALIBRATESTATUS
- `carrierNoiseRatio` (ufloatString): Used in TRACTSTAT, TRACTSTAT
- `centerFrequency` (ufloatString): Used in ITDETECTSTATUS, ITDETECTSTATUS
- `centerPointLatitude` (ufloatString): Used in TERRASTAR, TERRASTAR
- `centerPointLongitude` (ufloatString): Used in TERRASTAR, TERRASTAR
- `clockDrift` (udoubleString): Used in GIIITIMESOLUTION, GIIITIMESOLUTION
- `clockOffset` (udoubleString): Used in GIIITIMESOLUTION, GIIITIMESOLUTION
- `clockStatus` (uenumString): Used in TIME, TIME
- `comPort` (uenumString): Used in VERIPOSDECODERSTATUS, VERIPOSDECODERSTATUS
- `command` (ustringvariable): Used in GIIIRXCOMMANDS, GIIIRXCOMMANDS
- `component` (uenumString): Used in GIIICARDSTATUS, GIIICARDSTATUS
- `comport` (uenumString): Used in ALIGNAUTOMATION, ALIGNAUTOMATION
- `control` (uenumString): Used in AUTOSURVEY, AUTOSURVEY
- `corrections_port` (uenumString): Used in WIFIALIGNAUTOMATION, WIFIALIGNAUTOMATION
- `cutoff` (ufloatString): Used in TRACTSTAT, PSRDOP, TRACTSTAT, PSRDOP
- `datumId` (uenumString): Used in BESTPOS, MARKPOS, BESTPOS, MARKPOS
- `decoderChannel` (ushortString): Used in VERIPOSDECODERSTATUS, VERIPOSDECODERSTATUS
- `decoderSyncStatus` (ushortString): Used in VERIPOSDECODERSTATUS, VERIPOSDECODERSTATUS
- `description` (ustringvariable): Used in RXSTATUSEVENT, RXSTATUSEVENT
- `details` (uhex): Used in VERIPOSINFO, GIIIETHERNETSTATUS, VERIPOSINFO, GIIIETHERNETSTATUS
- `detectionType` (uenumString): Used in ITDETECTSTATUS, ITDETECTSTATUS
- `differentialAge` (ufloatString): Used in BESTPOS, MARKPOS, BESTPOS, MARKPOS
- `diskFullAction` (uenumString): Used in FILEROTATECONFIG, FILEROTATECONFIG
- `dnsserver` (uenumString): Used in DNSCONFIG, DNSCONFIG
- `dopp` (ufloatString): Used in GIIIMEASUREMENTDATA, GIIIMEASUREMENTDATA
- `doppler` (ufloatString): Used in TRACTSTAT, LBANDTRACKSTAT, TRACTSTAT, LBANDTRACKSTAT
- `eastOffset` (udoubleString): Used in BASEANTENNAPCO, THISANTENNAPCO, BASEANTENNAPCO, THISANTENNAPCO
- `eastVelDev` (ufloatString): Used in INSPVAX, INSPVAX
- `eastVelocity` (udoubleString): Used in INSPVA, INSPVAX, MARKPVA, INSPVA, INSPVAX, and 1 more
- `elevation` (udoubleString): Used in SATVIS2, SATVIS2
- `encryption` (uenumString): Used in WIFIAPSETTINGS, WIFIAPSETTINGS
- `endPoint` (ustringvariable): Used in ICOMCONFIG, ICOMCONFIG
- `endpoint` (ustringvariable): Used in NTRIPCONFIG, NTRIPCONFIG
- `ephAzimuth` (ufloatString): Used in GIIISATPOS, GIIISATPOS
- `ephDop` (ufloatString): Used in GIIISATPOS, GIIISATPOS
- `ephElevation` (ufloatString): Used in GIIISATPOS, GIIISATPOS
- `ephemValidity` (ushortString): Used in GIIISATPOS, GIIISATPOS, GIIISATPOS, GIIISATPOS
- `errorMsg` (ustringvariable): Used in FILESYSTEMSTATUS, FILETRANSFERSTATUS, FILESYSTEMSTATUS, FILETRANSFERSTATUS
- `estimatedPower` (ufloatString): Used in ITDETECTSTATUS, ITDETECTSTATUS
- `event` (uenumString): Used in RXSTATUSEVENT, RXSTATUSEVENT
- `extSolStat` (ucharString): Used in HEADING2, HEADING2
- `extendedSolution` (uhex): Used in INSPOSX, INSPOSX
- `extendedSolutionStatus` (uhex): Used in BESTPOS, MARKPOS, BESTPOS, MARKPOS
- `fanFailed` (ushortString): Used in GIIICARDSTATUS, GIIICARDSTATUS
- `fanSpeed` (ushortString): Used in GIIICARDSTATUS, GIIICARDSTATUS
- `featureStatus` (uenumString): Used in MODELFEATURE, MODELFEATURE
- `featureType` (uenumString): Used in MODELFEATURE, MODELFEATURE
- `fec` (uenumString): Used in SATEL4INFO, SATEL4INFO
- `fftSize` (uenumString): Used in ITSPECTRALANALYSIS, ITSPECTRALANALYSIS
- `fileName` (ustringvariable): Used in FILELIST, FILETRANSFERSTATUS, FILELIST, FILETRANSFERSTATUS
- `fileTransferStatus` (uenumString): Used in FILETRANSFERSTATUS, FILETRANSFERSTATUS
- `fileType` (uenumString): Used in FILELIST, FILELIST
- `frequency` (uenumString): Used in ITSPECTRALANALYSIS, BASEANTENNAPCO, THISANTENNAPCO, ITSPECTRALANALYSIS, BASEANTENNAPCO, and 1 more
- `frequencyStart` (ufloatString): Used in ITPSDFINAL, ITPSDDETECT, ITPSDFINAL, ITPSDDETECT
- `frequencyStep` (ufloatString): Used in ITBANDPASSFILTBANK, ITBANDPASSFILTBANK
- `frequencyType` (uenumString): Used in ITBANDPASSFILTBANK, ITBANDPASSFILTBANK
- `frontEndMode` (uenumString): Used in SKCALIBRATESTATUS, SKCALIBRATESTATUS
- `galAndBeiDouSigMask` (ucharString): Used in HEADING2, HEADING2
- `gateway` (ustringvariable): Used in IPCONFIG, IPCONFIG
- `gdop` (ufloatString): Used in PSRDOP, PSRDOP
