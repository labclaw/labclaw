# Device SOUL Template

> Copy this directory to devices/<device-name>/ and fill in.
> Every device is a "member" of the lab with its own identity and memory.

## Identity

- **Name:**
- **Type:** (camera / microscope / ephys-rig / behavioral-apparatus / stimulator / DAQ / other)
- **Model:**
- **Location:** (room, bench, rig number)
- **Serial number:**
- **Installed:** (date)

## Capabilities

- **Can observe:** (what data it produces — video, images, electrical signals, etc.)
- **Can control:** (what it can actuate — LED, valve, stage, laser, etc.)
- **Data format:** (output file formats — .avi, .tif, .oebin, .nwb, .abf, etc.)
- **Interface type:** (file-based / serial / network-API / GPIO / software-bridge)

## Protocols Supported

(Which lab protocols use this device, and in what role)

## Access Control

- **Read access:** (who can monitor — typically all members)
- **Control access:** (who can send commands — list of certified members)
- **Configure access:** (who can change settings — typically PI + technician)

## Known Quirks

(Important things anyone using this device should know)
