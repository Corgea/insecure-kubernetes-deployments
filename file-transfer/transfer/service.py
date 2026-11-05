"""Request handlers and storage helpers for the resumable file transfer service.

Clients upload a file in one of two ways:

* ``POST /transfers/upload`` with a multipart body, for files that fit in one
  request.
* ``PATCH /transfers/<id>`` with one chunk per request, for everything else.

Handlers take a :class:`~transfer.http.Request` and a :class:`Dependencies`
bundle and return a :class:`~transfer.http.Response`, so they can run behind any
WSGI or ASGI adapter.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from .http import Request, Response, UploadedFile
from .regions import UnknownRegion, resolve_region

logger = logging.getLogger(__name__)

MAX_CHUNK_BYTES = 16 * 1024 * 1024
MAX_SINGLE_REQUEST_BYTES = 64 * 1024 * 1024
DEFAULT_QUOTA_BYTES = 50 * 1024 * 1024 * 1024
TRANSFER_ID_PATTERN = re.compile(r"[0-9a-f]{32}")
REQUIRED_CHUNK_HEADERS = ("Upload-Offset", "Upload-Length", "Upload-Name")
TERMINAL_STATES = frozenset({"complete", "cancelled", "expired"})
UPLOAD_EXPIRY_SECONDS = 7 * 24 * 60 * 60
CHUNK_CONTENT_TYPE = "application/offset+octet-stream"


@dataclass(frozen=True)
class FileType:
    """What the service knows about one accepted file extension."""

    mime: str
    category: str
    max_mb: int


# Every extension the service accepts, with the media type recorded for it and
# the largest file allowed.
FILE_TYPES = {
    "123": FileType("application/vnd.lotus-1-2-3", "application", 2048),
    "3dml": FileType("text/vnd.in3d.3dml", "text", 64),
    "3ds": FileType("image/x-3ds", "image", 256),
    "3g2": FileType("video/3gpp2", "video", 4096),
    "3gp": FileType("video/3gpp", "video", 4096),
    "7z": FileType("application/x-7z-compressed", "application", 2048),
    "aab": FileType("application/x-authorware-bin", "application", 2048),
    "aac": FileType("audio/x-aac", "audio", 1024),
    "aam": FileType("application/x-authorware-map", "application", 2048),
    "aas": FileType("application/x-authorware-seg", "application", 2048),
    "abw": FileType("application/x-abiword", "application", 2048),
    "ac": FileType("application/pkix-attr-cert", "application", 2048),
    "acc": FileType("application/vnd.americandynamics.acc", "application", 2048),
    "ace": FileType("application/x-ace-compressed", "application", 2048),
    "acu": FileType("application/vnd.acucobol", "application", 2048),
    "acutc": FileType("application/vnd.acucorp", "application", 2048),
    "adp": FileType("audio/adpcm", "audio", 1024),
    "aep": FileType("application/vnd.audiograph", "application", 2048),
    "afm": FileType("application/x-font-type1", "application", 2048),
    "afp": FileType("application/vnd.ibm.modcap", "application", 2048),
    "ahead": FileType("application/vnd.ahead.space", "application", 2048),
    "ai": FileType("application/postscript", "application", 2048),
    "aif": FileType("audio/x-aiff", "audio", 1024),
    "aifc": FileType("audio/x-aiff", "audio", 1024),
    "aiff": FileType("audio/x-aiff", "audio", 1024),
    "air": FileType("application/vnd.adobe.air-application-installer-package+zip", "application", 2048),
    "ait": FileType("application/vnd.dvb.ait", "application", 2048),
    "ami": FileType("application/vnd.amiga.ami", "application", 2048),
    "apk": FileType("application/vnd.android.package-archive", "application", 2048),
    "appcache": FileType("text/cache-manifest", "text", 64),
    "application": FileType("application/x-ms-application", "application", 2048),
    "apr": FileType("application/vnd.lotus-approach", "application", 2048),
    "arc": FileType("application/x-freearc", "application", 2048),
    "asc": FileType("application/pgp-signature", "application", 2048),
    "asf": FileType("video/x-ms-asf", "video", 4096),
    "asm": FileType("text/x-asm", "text", 64),
    "aso": FileType("application/vnd.accpac.simply.aso", "application", 2048),
    "asx": FileType("video/x-ms-asf", "video", 4096),
    "atc": FileType("application/vnd.acucorp", "application", 2048),
    "atom": FileType("application/atom+xml", "application", 2048),
    "atomcat": FileType("application/atomcat+xml", "application", 2048),
    "atomsvc": FileType("application/atomsvc+xml", "application", 2048),
    "atx": FileType("application/vnd.antix.game-component", "application", 2048),
    "au": FileType("audio/basic", "audio", 1024),
    "avi": FileType("video/x-msvideo", "video", 4096),
    "avif": FileType("image/avif", "image", 256),
    "aw": FileType("application/applixware", "application", 2048),
    "azf": FileType("application/vnd.airzip.filesecure.azf", "application", 2048),
    "azs": FileType("application/vnd.airzip.filesecure.azs", "application", 2048),
    "azw": FileType("application/vnd.amazon.ebook", "application", 2048),
    "bat": FileType("application/x-msdownload", "application", 2048),
    "bcpio": FileType("application/x-bcpio", "application", 2048),
    "bdf": FileType("application/x-font-bdf", "application", 2048),
    "bdm": FileType("application/vnd.syncml.dm+wbxml", "application", 2048),
    "bed": FileType("application/vnd.realvnc.bed", "application", 2048),
    "bh2": FileType("application/vnd.fujitsu.oasysprs", "application", 2048),
    "bin": FileType("application/octet-stream", "application", 2048),
    "blb": FileType("application/x-blorb", "application", 2048),
    "blorb": FileType("application/x-blorb", "application", 2048),
    "bmi": FileType("application/vnd.bmi", "application", 2048),
    "bmp": FileType("image/bmp", "image", 256),
    "book": FileType("application/vnd.framemaker", "application", 2048),
    "box": FileType("application/vnd.previewsystems.box", "application", 2048),
    "boz": FileType("application/x-bzip2", "application", 2048),
    "bpk": FileType("application/octet-stream", "application", 2048),
    "btif": FileType("image/prs.btif", "image", 256),
    "bz": FileType("application/x-bzip", "application", 2048),
    "bz2": FileType("application/x-bzip2", "application", 2048),
    "c": FileType("text/x-c", "text", 64),
    "c11amc": FileType("application/vnd.cluetrust.cartomobile-config", "application", 2048),
    "c11amz": FileType("application/vnd.cluetrust.cartomobile-config-pkg", "application", 2048),
    "c4d": FileType("application/vnd.clonk.c4group", "application", 2048),
    "c4f": FileType("application/vnd.clonk.c4group", "application", 2048),
    "c4g": FileType("application/vnd.clonk.c4group", "application", 2048),
    "c4p": FileType("application/vnd.clonk.c4group", "application", 2048),
    "c4u": FileType("application/vnd.clonk.c4group", "application", 2048),
    "cab": FileType("application/vnd.ms-cab-compressed", "application", 2048),
    "caf": FileType("audio/x-caf", "audio", 1024),
    "cap": FileType("application/vnd.tcpdump.pcap", "application", 2048),
    "car": FileType("application/vnd.curl.car", "application", 2048),
    "cat": FileType("application/vnd.ms-pki.seccat", "application", 2048),
    "cb7": FileType("application/x-cbr", "application", 2048),
    "cba": FileType("application/x-cbr", "application", 2048),
    "cbr": FileType("application/x-cbr", "application", 2048),
    "cbt": FileType("application/x-cbr", "application", 2048),
    "cbz": FileType("application/x-cbr", "application", 2048),
    "cc": FileType("text/x-c", "text", 64),
    "cct": FileType("application/x-director", "application", 2048),
    "ccxml": FileType("application/ccxml+xml", "application", 2048),
    "cdbcmsg": FileType("application/vnd.contact.cmsg", "application", 2048),
    "cdf": FileType("application/x-netcdf", "application", 2048),
    "cdkey": FileType("application/vnd.mediastation.cdkey", "application", 2048),
    "cdmia": FileType("application/cdmi-capability", "application", 2048),
    "cdmic": FileType("application/cdmi-container", "application", 2048),
    "cdmid": FileType("application/cdmi-domain", "application", 2048),
    "cdmio": FileType("application/cdmi-object", "application", 2048),
    "cdmiq": FileType("application/cdmi-queue", "application", 2048),
    "cdx": FileType("chemical/x-cdx", "chemical", 64),
    "cdxml": FileType("application/vnd.chemdraw+xml", "application", 2048),
    "cdy": FileType("application/vnd.cinderella", "application", 2048),
    "cer": FileType("application/pkix-cert", "application", 2048),
    "cfs": FileType("application/x-cfs-compressed", "application", 2048),
    "cgm": FileType("image/cgm", "image", 256),
    "chat": FileType("application/x-chat", "application", 2048),
    "chm": FileType("application/vnd.ms-htmlhelp", "application", 2048),
    "chrt": FileType("application/vnd.kde.kchart", "application", 2048),
    "cif": FileType("chemical/x-cif", "chemical", 64),
    "cii": FileType("application/vnd.anser-web-certificate-issue-initiation", "application", 2048),
    "cil": FileType("application/vnd.ms-artgalry", "application", 2048),
    "cla": FileType("application/vnd.claymore", "application", 2048),
    "class": FileType("application/java-vm", "application", 2048),
    "clkk": FileType("application/vnd.crick.clicker.keyboard", "application", 2048),
    "clkp": FileType("application/vnd.crick.clicker.palette", "application", 2048),
    "clkt": FileType("application/vnd.crick.clicker.template", "application", 2048),
    "clkw": FileType("application/vnd.crick.clicker.wordbank", "application", 2048),
    "clkx": FileType("application/vnd.crick.clicker", "application", 2048),
    "clp": FileType("application/x-msclip", "application", 2048),
    "cmc": FileType("application/vnd.cosmocaller", "application", 2048),
    "cmdf": FileType("chemical/x-cmdf", "chemical", 64),
    "cml": FileType("chemical/x-cml", "chemical", 64),
    "cmp": FileType("application/vnd.yellowriver-custom-menu", "application", 2048),
    "cmx": FileType("image/x-cmx", "image", 256),
    "cod": FileType("application/vnd.rim.cod", "application", 2048),
    "com": FileType("application/x-msdownload", "application", 2048),
    "conf": FileType("text/plain", "text", 64),
    "cpio": FileType("application/x-cpio", "application", 2048),
    "cpp": FileType("text/x-c", "text", 64),
    "cpt": FileType("application/mac-compactpro", "application", 2048),
    "crd": FileType("application/x-mscardfile", "application", 2048),
    "crl": FileType("application/pkix-crl", "application", 2048),
    "crt": FileType("application/x-x509-ca-cert", "application", 2048),
    "cryptonote": FileType("application/vnd.rig.cryptonote", "application", 2048),
    "csh": FileType("application/x-csh", "application", 2048),
    "csml": FileType("chemical/x-csml", "chemical", 64),
    "csp": FileType("application/vnd.commonspace", "application", 2048),
    "css": FileType("text/css", "text", 64),
    "cst": FileType("application/x-director", "application", 2048),
    "csv": FileType("text/csv", "text", 64),
    "cu": FileType("application/cu-seeme", "application", 2048),
    "curl": FileType("text/vnd.curl", "text", 64),
    "cww": FileType("application/prs.cww", "application", 2048),
    "cxt": FileType("application/x-director", "application", 2048),
    "cxx": FileType("text/x-c", "text", 64),
    "dae": FileType("model/vnd.collada+xml", "model", 512),
    "daf": FileType("application/vnd.mobius.daf", "application", 2048),
    "dart": FileType("application/vnd.dart", "application", 2048),
    "dataless": FileType("application/vnd.fdsn.seed", "application", 2048),
    "davmount": FileType("application/davmount+xml", "application", 2048),
    "dbk": FileType("application/docbook+xml", "application", 2048),
    "dcr": FileType("application/x-director", "application", 2048),
    "dcurl": FileType("text/vnd.curl.dcurl", "text", 64),
    "dd2": FileType("application/vnd.oma.dd2+xml", "application", 2048),
    "ddd": FileType("application/vnd.fujixerox.ddd", "application", 2048),
    "deb": FileType("application/x-debian-package", "application", 2048),
    "def": FileType("text/plain", "text", 64),
    "deploy": FileType("application/octet-stream", "application", 2048),
    "der": FileType("application/x-x509-ca-cert", "application", 2048),
    "dfac": FileType("application/vnd.dreamfactory", "application", 2048),
    "dgc": FileType("application/x-dgc-compressed", "application", 2048),
    "dic": FileType("text/x-c", "text", 64),
    "dif": FileType("video/x-dv", "video", 4096),
    "dir": FileType("application/x-director", "application", 2048),
    "dis": FileType("application/vnd.mobius.dis", "application", 2048),
    "dist": FileType("application/octet-stream", "application", 2048),
    "distz": FileType("application/octet-stream", "application", 2048),
    "djv": FileType("image/vnd.djvu", "image", 256),
    "djvu": FileType("image/vnd.djvu", "image", 256),
    "dll": FileType("application/x-msdownload", "application", 2048),
    "dmg": FileType("application/x-apple-diskimage", "application", 2048),
    "dmp": FileType("application/vnd.tcpdump.pcap", "application", 2048),
    "dms": FileType("application/octet-stream", "application", 2048),
    "dna": FileType("application/vnd.dna", "application", 2048),
    "doc": FileType("application/msword", "application", 2048),
    "docm": FileType("application/vnd.ms-word.document.macroenabled.12", "application", 2048),
    "docx": FileType("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application", 2048),
    "dot": FileType("application/msword", "application", 2048),
    "dotm": FileType("application/vnd.ms-word.template.macroenabled.12", "application", 2048),
    "dotx": FileType("application/vnd.openxmlformats-officedocument.wordprocessingml.template", "application", 2048),
    "dp": FileType("application/vnd.osgi.dp", "application", 2048),
    "dpg": FileType("application/vnd.dpgraph", "application", 2048),
    "dra": FileType("audio/vnd.dra", "audio", 1024),
    "dsc": FileType("text/prs.lines.tag", "text", 64),
    "dssc": FileType("application/dssc+der", "application", 2048),
    "dtb": FileType("application/x-dtbook+xml", "application", 2048),
    "dtd": FileType("application/xml-dtd", "application", 2048),
    "dts": FileType("audio/vnd.dts", "audio", 1024),
    "dtshd": FileType("audio/vnd.dts.hd", "audio", 1024),
    "dump": FileType("application/octet-stream", "application", 2048),
    "dv": FileType("video/x-dv", "video", 4096),
    "dvb": FileType("video/vnd.dvb.file", "video", 4096),
    "dvi": FileType("application/x-dvi", "application", 2048),
    "dwf": FileType("model/vnd.dwf", "model", 512),
    "dwg": FileType("image/vnd.dwg", "image", 256),
    "dxf": FileType("image/vnd.dxf", "image", 256),
    "dxp": FileType("application/vnd.spotfire.dxp", "application", 2048),
    "dxr": FileType("application/x-director", "application", 2048),
    "ecelp4800": FileType("audio/vnd.nuera.ecelp4800", "audio", 1024),
    "ecelp7470": FileType("audio/vnd.nuera.ecelp7470", "audio", 1024),
    "ecelp9600": FileType("audio/vnd.nuera.ecelp9600", "audio", 1024),
    "ecma": FileType("application/ecmascript", "application", 2048),
    "edm": FileType("application/vnd.novadigm.edm", "application", 2048),
    "edx": FileType("application/vnd.novadigm.edx", "application", 2048),
    "efif": FileType("application/vnd.picsel", "application", 2048),
    "ei6": FileType("application/vnd.pg.osasli", "application", 2048),
    "elc": FileType("application/octet-stream", "application", 2048),
    "emf": FileType("application/x-msmetafile", "application", 2048),
    "eml": FileType("message/rfc822", "message", 64),
    "emma": FileType("application/emma+xml", "application", 2048),
    "emz": FileType("application/x-msmetafile", "application", 2048),
    "eol": FileType("audio/vnd.digital-winds", "audio", 1024),
    "eot": FileType("application/vnd.ms-fontobject", "application", 2048),
    "eps": FileType("application/postscript", "application", 2048),
    "epub": FileType("application/epub+zip", "application", 2048),
    "es3": FileType("application/vnd.eszigno3+xml", "application", 2048),
    "esa": FileType("application/vnd.osgi.subsystem", "application", 2048),
    "esf": FileType("application/vnd.epson.esf", "application", 2048),
    "et3": FileType("application/vnd.eszigno3+xml", "application", 2048),
    "etx": FileType("text/x-setext", "text", 64),
    "eva": FileType("application/x-eva", "application", 2048),
    "evy": FileType("application/x-envoy", "application", 2048),
    "exe": FileType("application/x-msdownload", "application", 2048),
    "exi": FileType("application/exi", "application", 2048),
    "ext": FileType("application/vnd.novadigm.ext", "application", 2048),
    "ez": FileType("application/andrew-inset", "application", 2048),
    "ez2": FileType("application/vnd.ezpix-album", "application", 2048),
    "ez3": FileType("application/vnd.ezpix-package", "application", 2048),
    "f": FileType("text/x-fortran", "text", 64),
    "f4v": FileType("video/x-f4v", "video", 4096),
    "f77": FileType("text/x-fortran", "text", 64),
    "f90": FileType("text/x-fortran", "text", 64),
    "fbs": FileType("image/vnd.fastbidsheet", "image", 256),
    "fcdt": FileType("application/vnd.adobe.formscentral.fcdt", "application", 2048),
    "fcs": FileType("application/vnd.isac.fcs", "application", 2048),
    "fdf": FileType("application/vnd.fdf", "application", 2048),
    "fe_launch": FileType("application/vnd.denovo.fcselayout-link", "application", 2048),
    "fg5": FileType("application/vnd.fujitsu.oasysgp", "application", 2048),
    "fgd": FileType("application/x-director", "application", 2048),
    "fh": FileType("image/x-freehand", "image", 256),
    "fh4": FileType("image/x-freehand", "image", 256),
    "fh5": FileType("image/x-freehand", "image", 256),
    "fh7": FileType("image/x-freehand", "image", 256),
    "fhc": FileType("image/x-freehand", "image", 256),
    "fig": FileType("application/x-xfig", "application", 2048),
    "flac": FileType("audio/x-flac", "audio", 1024),
    "fli": FileType("video/x-fli", "video", 4096),
    "flo": FileType("application/vnd.micrografx.flo", "application", 2048),
    "flv": FileType("video/x-flv", "video", 4096),
    "flw": FileType("application/vnd.kde.kivio", "application", 2048),
    "flx": FileType("text/vnd.fmi.flexstor", "text", 64),
    "fly": FileType("text/vnd.fly", "text", 64),
    "fm": FileType("application/vnd.framemaker", "application", 2048),
    "fnc": FileType("application/vnd.frogans.fnc", "application", 2048),
    "for": FileType("text/x-fortran", "text", 64),
    "fpx": FileType("image/vnd.fpx", "image", 256),
    "frame": FileType("application/vnd.framemaker", "application", 2048),
    "fsc": FileType("application/vnd.fsc.weblaunch", "application", 2048),
    "fst": FileType("image/vnd.fst", "image", 256),
    "ftc": FileType("application/vnd.fluxtime.clip", "application", 2048),
    "fti": FileType("application/vnd.anser-web-funds-transfer-initiation", "application", 2048),
    "fvt": FileType("video/vnd.fvt", "video", 4096),
    "fxp": FileType("application/vnd.adobe.fxp", "application", 2048),
    "fxpl": FileType("application/vnd.adobe.fxp", "application", 2048),
    "fzs": FileType("application/vnd.fuzzysheet", "application", 2048),
    "g2w": FileType("application/vnd.geoplan", "application", 2048),
    "g3": FileType("image/g3fax", "image", 256),
    "g3w": FileType("application/vnd.geospace", "application", 2048),
    "gac": FileType("application/vnd.groove-account", "application", 2048),
    "gam": FileType("application/x-tads", "application", 2048),
    "gbr": FileType("application/rpki-ghostbusters", "application", 2048),
    "gca": FileType("application/x-gca-compressed", "application", 2048),
    "gdl": FileType("model/vnd.gdl", "model", 512),
    "geo": FileType("application/vnd.dynageo", "application", 2048),
    "gex": FileType("application/vnd.geometry-explorer", "application", 2048),
    "ggb": FileType("application/vnd.geogebra.file", "application", 2048),
    "ggs": FileType("application/vnd.geogebra.slides", "application", 2048),
    "ggt": FileType("application/vnd.geogebra.tool", "application", 2048),
    "ghf": FileType("application/vnd.groove-help", "application", 2048),
    "gif": FileType("image/gif", "image", 256),
    "gim": FileType("application/vnd.groove-identity-message", "application", 2048),
    "gml": FileType("application/gml+xml", "application", 2048),
    "gmx": FileType("application/vnd.gmx", "application", 2048),
    "gnumeric": FileType("application/x-gnumeric", "application", 2048),
    "gph": FileType("application/vnd.flographit", "application", 2048),
    "gpx": FileType("application/gpx+xml", "application", 2048),
    "gqf": FileType("application/vnd.grafeq", "application", 2048),
    "gqs": FileType("application/vnd.grafeq", "application", 2048),
    "gram": FileType("application/srgs", "application", 2048),
    "gramps": FileType("application/x-gramps-xml", "application", 2048),
    "gre": FileType("application/vnd.geometry-explorer", "application", 2048),
    "grv": FileType("application/vnd.groove-injector", "application", 2048),
    "grxml": FileType("application/srgs+xml", "application", 2048),
    "gsf": FileType("application/x-font-ghostscript", "application", 2048),
    "gtar": FileType("application/x-gtar", "application", 2048),
    "gtm": FileType("application/vnd.groove-tool-message", "application", 2048),
    "gtw": FileType("model/vnd.gtw", "model", 512),
    "gv": FileType("text/vnd.graphviz", "text", 64),
    "gxf": FileType("application/gxf", "application", 2048),
    "gxt": FileType("application/vnd.geonext", "application", 2048),
    "h": FileType("text/x-c", "text", 64),
    "h261": FileType("video/h261", "video", 4096),
    "h263": FileType("video/h263", "video", 4096),
    "h264": FileType("video/h264", "video", 4096),
    "hal": FileType("application/vnd.hal+xml", "application", 2048),
    "hbci": FileType("application/vnd.hbci", "application", 2048),
    "hdf": FileType("application/x-hdf", "application", 2048),
    "hh": FileType("text/x-c", "text", 64),
    "hlp": FileType("application/winhlp", "application", 2048),
    "hpgl": FileType("application/vnd.hp-hpgl", "application", 2048),
    "hpid": FileType("application/vnd.hp-hpid", "application", 2048),
    "hps": FileType("application/vnd.hp-hps", "application", 2048),
    "hqx": FileType("application/mac-binhex40", "application", 2048),
    "htke": FileType("application/vnd.kenameaapp", "application", 2048),
    "htm": FileType("text/html", "text", 64),
    "html": FileType("text/html", "text", 64),
    "hvd": FileType("application/vnd.yamaha.hv-dic", "application", 2048),
    "hvp": FileType("application/vnd.yamaha.hv-voice", "application", 2048),
    "hvs": FileType("application/vnd.yamaha.hv-script", "application", 2048),
    "i2g": FileType("application/vnd.intergeo", "application", 2048),
    "icc": FileType("application/vnd.iccprofile", "application", 2048),
    "ice": FileType("x-conference/x-cooltalk", "x-conference", 64),
    "icm": FileType("application/vnd.iccprofile", "application", 2048),
    "ico": FileType("image/x-icon", "image", 256),
    "ics": FileType("text/calendar", "text", 64),
    "ief": FileType("image/ief", "image", 256),
    "ifb": FileType("text/calendar", "text", 64),
    "ifm": FileType("application/vnd.shana.informed.formdata", "application", 2048),
    "iges": FileType("model/iges", "model", 512),
    "igl": FileType("application/vnd.igloader", "application", 2048),
    "igm": FileType("application/vnd.insors.igm", "application", 2048),
    "igs": FileType("model/iges", "model", 512),
    "igx": FileType("application/vnd.micrografx.igx", "application", 2048),
    "iif": FileType("application/vnd.shana.informed.interchange", "application", 2048),
    "imp": FileType("application/vnd.accpac.simply.imp", "application", 2048),
    "ims": FileType("application/vnd.ms-ims", "application", 2048),
    "in": FileType("text/plain", "text", 64),
    "ink": FileType("application/inkml+xml", "application", 2048),
    "inkml": FileType("application/inkml+xml", "application", 2048),
    "install": FileType("application/x-install-instructions", "application", 2048),
    "iota": FileType("application/vnd.astraea-software.iota", "application", 2048),
    "ipfix": FileType("application/ipfix", "application", 2048),
    "ipk": FileType("application/vnd.shana.informed.package", "application", 2048),
    "irm": FileType("application/vnd.ibm.rights-management", "application", 2048),
    "irp": FileType("application/vnd.irepository.package+xml", "application", 2048),
    "iso": FileType("application/x-iso9660-image", "application", 2048),
    "itp": FileType("application/vnd.shana.informed.formtemplate", "application", 2048),
    "ivp": FileType("application/vnd.immervision-ivp", "application", 2048),
    "ivu": FileType("application/vnd.immervision-ivu", "application", 2048),
    "jad": FileType("text/vnd.sun.j2me.app-descriptor", "text", 64),
    "jam": FileType("application/vnd.jam", "application", 2048),
    "jar": FileType("application/java-archive", "application", 2048),
    "java": FileType("text/x-java-source", "text", 64),
    "jisp": FileType("application/vnd.jisp", "application", 2048),
    "jlt": FileType("application/vnd.hp-jlyt", "application", 2048),
    "jnlp": FileType("application/x-java-jnlp-file", "application", 2048),
    "joda": FileType("application/vnd.joost.joda-archive", "application", 2048),
    "jp2": FileType("image/jp2", "image", 256),
    "jpe": FileType("image/jpeg", "image", 256),
    "jpeg": FileType("image/jpeg", "image", 256),
    "jpg": FileType("image/jpeg", "image", 256),
    "jpgm": FileType("video/jpm", "video", 4096),
    "jpgv": FileType("video/jpeg", "video", 4096),
    "jpm": FileType("video/jpm", "video", 4096),
    "js": FileType("text/javascript", "text", 64),
    "json": FileType("application/json", "application", 2048),
    "jsonml": FileType("application/jsonml+json", "application", 2048),
    "kar": FileType("audio/midi", "audio", 1024),
    "karbon": FileType("application/vnd.kde.karbon", "application", 2048),
    "kfo": FileType("application/vnd.kde.kformula", "application", 2048),
    "kia": FileType("application/vnd.kidspiration", "application", 2048),
    "kml": FileType("application/vnd.google-earth.kml+xml", "application", 2048),
    "kmz": FileType("application/vnd.google-earth.kmz", "application", 2048),
    "kne": FileType("application/vnd.kinar", "application", 2048),
    "knp": FileType("application/vnd.kinar", "application", 2048),
    "kon": FileType("application/vnd.kde.kontour", "application", 2048),
    "kpr": FileType("application/vnd.kde.kpresenter", "application", 2048),
    "kpt": FileType("application/vnd.kde.kpresenter", "application", 2048),
    "kpxx": FileType("application/vnd.ds-keypoint", "application", 2048),
    "ksp": FileType("application/vnd.kde.kspread", "application", 2048),
    "ktr": FileType("application/vnd.kahootz", "application", 2048),
    "ktx": FileType("image/ktx", "image", 256),
    "ktz": FileType("application/vnd.kahootz", "application", 2048),
    "kwd": FileType("application/vnd.kde.kword", "application", 2048),
    "kwt": FileType("application/vnd.kde.kword", "application", 2048),
    "lasxml": FileType("application/vnd.las.las+xml", "application", 2048),
    "latex": FileType("application/x-latex", "application", 2048),
    "lbd": FileType("application/vnd.llamagraphics.life-balance.desktop", "application", 2048),
    "lbe": FileType("application/vnd.llamagraphics.life-balance.exchange+xml", "application", 2048),
    "les": FileType("application/vnd.hhe.lesson-player", "application", 2048),
    "lha": FileType("application/x-lzh-compressed", "application", 2048),
    "link66": FileType("application/vnd.route66.link66+xml", "application", 2048),
    "list": FileType("text/plain", "text", 64),
    "list3820": FileType("application/vnd.ibm.modcap", "application", 2048),
    "listafp": FileType("application/vnd.ibm.modcap", "application", 2048),
    "lnk": FileType("application/x-ms-shortcut", "application", 2048),
    "log": FileType("text/plain", "text", 64),
    "lostxml": FileType("application/lost+xml", "application", 2048),
    "lrf": FileType("application/octet-stream", "application", 2048),
    "lrm": FileType("application/vnd.ms-lrm", "application", 2048),
    "ltf": FileType("application/vnd.frogans.ltf", "application", 2048),
    "lvp": FileType("audio/vnd.lucent.voice", "audio", 1024),
    "lwp": FileType("application/vnd.lotus-wordpro", "application", 2048),
    "lzh": FileType("application/x-lzh-compressed", "application", 2048),
    "m13": FileType("application/x-msmediaview", "application", 2048),
    "m14": FileType("application/x-msmediaview", "application", 2048),
    "m1v": FileType("video/mpeg", "video", 4096),
    "m21": FileType("application/mp21", "application", 2048),
    "m2a": FileType("audio/mpeg", "audio", 1024),
    "m2t": FileType("video/mp2t", "video", 4096),
    "m2ts": FileType("video/mp2t", "video", 4096),
    "m2v": FileType("video/mpeg", "video", 4096),
    "m3a": FileType("audio/mpeg", "audio", 1024),
    "m3u": FileType("audio/x-mpegurl", "audio", 1024),
    "m3u8": FileType("application/vnd.apple.mpegurl", "application", 2048),
    "m4a": FileType("audio/mp4", "audio", 1024),
    "m4p": FileType("audio/mp4a-latm", "audio", 1024),
    "m4u": FileType("video/vnd.mpegurl", "video", 4096),
    "m4v": FileType("video/mp4", "video", 4096),
    "ma": FileType("application/mathematica", "application", 2048),
    "mac": FileType("image/x-macpaint", "image", 256),
    "mads": FileType("application/mads+xml", "application", 2048),
    "mag": FileType("application/vnd.ecowin.chart", "application", 2048),
    "maker": FileType("application/vnd.framemaker", "application", 2048),
    "man": FileType("text/troff", "text", 64),
    "manifest": FileType("text/cache-manifest", "text", 64),
    "mar": FileType("application/octet-stream", "application", 2048),
    "mathml": FileType("application/mathml+xml", "application", 2048),
    "mb": FileType("application/mathematica", "application", 2048),
    "mbk": FileType("application/vnd.mobius.mbk", "application", 2048),
    "mbox": FileType("application/mbox", "application", 2048),
    "mc1": FileType("application/vnd.medcalcdata", "application", 2048),
    "mcd": FileType("application/vnd.mcd", "application", 2048),
    "mcurl": FileType("text/vnd.curl.mcurl", "text", 64),
    "mdb": FileType("application/x-msaccess", "application", 2048),
    "mdi": FileType("image/vnd.ms-modi", "image", 256),
    "me": FileType("text/troff", "text", 64),
    "mesh": FileType("model/mesh", "model", 512),
    "meta4": FileType("application/metalink4+xml", "application", 2048),
    "metalink": FileType("application/metalink+xml", "application", 2048),
    "mets": FileType("application/mets+xml", "application", 2048),
    "mfm": FileType("application/vnd.mfmp", "application", 2048),
    "mft": FileType("application/rpki-manifest", "application", 2048),
    "mgp": FileType("application/vnd.osgeo.mapguide.package", "application", 2048),
    "mgz": FileType("application/vnd.proteus.magazine", "application", 2048),
    "mid": FileType("audio/midi", "audio", 1024),
    "midi": FileType("audio/midi", "audio", 1024),
    "mie": FileType("application/x-mie", "application", 2048),
    "mif": FileType("application/vnd.mif", "application", 2048),
    "mime": FileType("message/rfc822", "message", 64),
    "mj2": FileType("video/mj2", "video", 4096),
    "mjp2": FileType("video/mj2", "video", 4096),
    "mjs": FileType("text/javascript", "text", 64),
    "mk3d": FileType("video/x-matroska", "video", 4096),
    "mka": FileType("audio/x-matroska", "audio", 1024),
    "mks": FileType("video/x-matroska", "video", 4096),
    "mkv": FileType("video/x-matroska", "video", 4096),
    "mlp": FileType("application/vnd.dolby.mlp", "application", 2048),
    "mmd": FileType("application/vnd.chipnuts.karaoke-mmd", "application", 2048),
    "mmf": FileType("application/vnd.smaf", "application", 2048),
    "mmr": FileType("image/vnd.fujixerox.edmics-mmr", "image", 256),
    "mng": FileType("video/x-mng", "video", 4096),
    "mny": FileType("application/x-msmoney", "application", 2048),
    "mobi": FileType("application/x-mobipocket-ebook", "application", 2048),
    "mobipocket-ebook": FileType("application/octet-stream", "application", 2048),
    "mods": FileType("application/mods+xml", "application", 2048),
    "mov": FileType("video/quicktime", "video", 4096),
    "movie": FileType("video/x-sgi-movie", "video", 4096),
    "mp2": FileType("audio/mpeg", "audio", 1024),
    "mp21": FileType("application/mp21", "application", 2048),
    "mp2a": FileType("audio/mpeg", "audio", 1024),
    "mp3": FileType("audio/mpeg", "audio", 1024),
    "mp4": FileType("video/mp4", "video", 4096),
    "mp4a": FileType("audio/mp4", "audio", 1024),
    "mp4s": FileType("application/mp4", "application", 2048),
    "mp4v": FileType("video/mp4", "video", 4096),
    "mpc": FileType("application/vnd.mophun.certificate", "application", 2048),
    "mpe": FileType("video/mpeg", "video", 4096),
    "mpeg": FileType("video/mpeg", "video", 4096),
    "mpg": FileType("video/mpeg", "video", 4096),
    "mpg4": FileType("video/mp4", "video", 4096),
    "mpga": FileType("audio/mpeg", "audio", 1024),
    "mpkg": FileType("application/vnd.apple.installer+xml", "application", 2048),
    "mpm": FileType("application/vnd.blueice.multipass", "application", 2048),
    "mpn": FileType("application/vnd.mophun.application", "application", 2048),
    "mpp": FileType("application/vnd.ms-project", "application", 2048),
    "mpt": FileType("application/vnd.ms-project", "application", 2048),
    "mpy": FileType("application/vnd.ibm.minipay", "application", 2048),
    "mqy": FileType("application/vnd.mobius.mqy", "application", 2048),
    "mrc": FileType("application/marc", "application", 2048),
    "mrcx": FileType("application/marcxml+xml", "application", 2048),
    "ms": FileType("text/troff", "text", 64),
    "mscml": FileType("application/mediaservercontrol+xml", "application", 2048),
    "mseed": FileType("application/vnd.fdsn.mseed", "application", 2048),
    "mseq": FileType("application/vnd.mseq", "application", 2048),
    "msf": FileType("application/vnd.epson.msf", "application", 2048),
    "msh": FileType("model/mesh", "model", 512),
    "msi": FileType("application/x-msdownload", "application", 2048),
    "msl": FileType("application/vnd.mobius.msl", "application", 2048),
    "msty": FileType("application/vnd.muvee.style", "application", 2048),
    "mts": FileType("video/mp2t", "video", 4096),
    "mus": FileType("application/vnd.musician", "application", 2048),
    "musicxml": FileType("application/vnd.recordare.musicxml+xml", "application", 2048),
    "mvb": FileType("application/x-msmediaview", "application", 2048),
    "mwf": FileType("application/vnd.mfer", "application", 2048),
    "mxf": FileType("application/mxf", "application", 2048),
    "mxl": FileType("application/vnd.recordare.musicxml", "application", 2048),
    "mxml": FileType("application/xv+xml", "application", 2048),
    "mxs": FileType("application/vnd.triscape.mxs", "application", 2048),
    "mxu": FileType("video/vnd.mpegurl", "video", 4096),
    "n-gage": FileType("application/vnd.nokia.n-gage.symbian.install", "application", 2048),
    "n3": FileType("text/n3", "text", 64),
    "nb": FileType("application/mathematica", "application", 2048),
    "nbp": FileType("application/vnd.wolfram.player", "application", 2048),
    "nc": FileType("application/x-netcdf", "application", 2048),
    "ncx": FileType("application/x-dtbncx+xml", "application", 2048),
    "nfo": FileType("text/x-nfo", "text", 64),
    "ngdat": FileType("application/vnd.nokia.n-gage.data", "application", 2048),
    "nitf": FileType("application/vnd.nitf", "application", 2048),
    "nlu": FileType("application/vnd.neurolanguage.nlu", "application", 2048),
    "nml": FileType("application/vnd.enliven", "application", 2048),
    "nnd": FileType("application/vnd.noblenet-directory", "application", 2048),
    "nns": FileType("application/vnd.noblenet-sealer", "application", 2048),
    "nnw": FileType("application/vnd.noblenet-web", "application", 2048),
    "npx": FileType("image/vnd.net-fpx", "image", 256),
    "nsc": FileType("application/x-conference", "application", 2048),
    "nsf": FileType("application/vnd.lotus-notes", "application", 2048),
    "ntf": FileType("application/vnd.nitf", "application", 2048),
    "nzb": FileType("application/x-nzb", "application", 2048),
    "oa2": FileType("application/vnd.fujitsu.oasys2", "application", 2048),
    "oa3": FileType("application/vnd.fujitsu.oasys3", "application", 2048),
    "oas": FileType("application/vnd.fujitsu.oasys", "application", 2048),
    "obd": FileType("application/x-msbinder", "application", 2048),
    "obj": FileType("application/x-tgif", "application", 2048),
    "oda": FileType("application/oda", "application", 2048),
    "odb": FileType("application/vnd.oasis.opendocument.database", "application", 2048),
    "odc": FileType("application/vnd.oasis.opendocument.chart", "application", 2048),
    "odf": FileType("application/vnd.oasis.opendocument.formula", "application", 2048),
    "odft": FileType("application/vnd.oasis.opendocument.formula-template", "application", 2048),
    "odg": FileType("application/vnd.oasis.opendocument.graphics", "application", 2048),
    "odi": FileType("application/vnd.oasis.opendocument.image", "application", 2048),
    "odm": FileType("application/vnd.oasis.opendocument.text-master", "application", 2048),
    "odp": FileType("application/vnd.oasis.opendocument.presentation", "application", 2048),
    "ods": FileType("application/vnd.oasis.opendocument.spreadsheet", "application", 2048),
    "odt": FileType("application/vnd.oasis.opendocument.text", "application", 2048),
    "oga": FileType("audio/ogg", "audio", 1024),
    "ogg": FileType("audio/ogg", "audio", 1024),
    "ogv": FileType("video/ogg", "video", 4096),
    "ogx": FileType("application/ogg", "application", 2048),
    "omdoc": FileType("application/omdoc+xml", "application", 2048),
    "onepkg": FileType("application/onenote", "application", 2048),
    "onetmp": FileType("application/onenote", "application", 2048),
    "onetoc": FileType("application/onenote", "application", 2048),
    "onetoc2": FileType("application/onenote", "application", 2048),
    "opf": FileType("application/oebps-package+xml", "application", 2048),
    "opml": FileType("text/x-opml", "text", 64),
    "oprc": FileType("application/vnd.palm", "application", 2048),
    "opus": FileType("audio/ogg", "audio", 1024),
    "org": FileType("application/vnd.lotus-organizer", "application", 2048),
    "osf": FileType("application/vnd.yamaha.openscoreformat", "application", 2048),
    "osfpvg": FileType("application/vnd.yamaha.openscoreformat.osfpvg+xml", "application", 2048),
    "otc": FileType("application/vnd.oasis.opendocument.chart-template", "application", 2048),
    "otf": FileType("font/otf", "font", 64),
    "otg": FileType("application/vnd.oasis.opendocument.graphics-template", "application", 2048),
    "oth": FileType("application/vnd.oasis.opendocument.text-web", "application", 2048),
    "oti": FileType("application/vnd.oasis.opendocument.image-template", "application", 2048),
    "otp": FileType("application/vnd.oasis.opendocument.presentation-template", "application", 2048),
    "ots": FileType("application/vnd.oasis.opendocument.spreadsheet-template", "application", 2048),
    "ott": FileType("application/vnd.oasis.opendocument.text-template", "application", 2048),
    "oxps": FileType("application/oxps", "application", 2048),
    "oxt": FileType("application/vnd.openofficeorg.extension", "application", 2048),
    "p": FileType("text/x-pascal", "text", 64),
    "p10": FileType("application/pkcs10", "application", 2048),
    "p12": FileType("application/x-pkcs12", "application", 2048),
    "p7b": FileType("application/x-pkcs7-certificates", "application", 2048),
    "p7c": FileType("application/pkcs7-mime", "application", 2048),
    "p7m": FileType("application/pkcs7-mime", "application", 2048),
    "p7r": FileType("application/x-pkcs7-certreqresp", "application", 2048),
    "p7s": FileType("application/pkcs7-signature", "application", 2048),
    "p8": FileType("application/pkcs8", "application", 2048),
    "pas": FileType("text/x-pascal", "text", 64),
    "paw": FileType("application/vnd.pawaafile", "application", 2048),
    "pbd": FileType("application/vnd.powerbuilder6", "application", 2048),
    "pbm": FileType("image/x-portable-bitmap", "image", 256),
    "pcap": FileType("application/vnd.tcpdump.pcap", "application", 2048),
    "pcf": FileType("application/x-font-pcf", "application", 2048),
    "pcl": FileType("application/vnd.hp-pcl", "application", 2048),
    "pclxl": FileType("application/vnd.hp-pclxl", "application", 2048),
    "pct": FileType("image/pict", "image", 256),
    "pcurl": FileType("application/vnd.curl.pcurl", "application", 2048),
    "pcx": FileType("image/x-pcx", "image", 256),
    "pdb": FileType("application/vnd.palm", "application", 2048),
    "pdf": FileType("application/pdf", "application", 2048),
    "pfa": FileType("application/x-font-type1", "application", 2048),
    "pfb": FileType("application/x-font-type1", "application", 2048),
    "pfm": FileType("application/x-font-type1", "application", 2048),
    "pfr": FileType("application/font-tdpfr", "application", 2048),
    "pfx": FileType("application/x-pkcs12", "application", 2048),
    "pgm": FileType("image/x-portable-graymap", "image", 256),
    "pgn": FileType("application/x-chess-pgn", "application", 2048),
    "pgp": FileType("application/pgp-encrypted", "application", 2048),
    "pic": FileType("image/pict", "image", 256),
    "pict": FileType("image/pict", "image", 256),
    "pkg": FileType("application/octet-stream", "application", 2048),
    "pki": FileType("application/pkixcmp", "application", 2048),
    "pkipath": FileType("application/pkix-pkipath", "application", 2048),
    "plb": FileType("application/vnd.3gpp.pic-bw-large", "application", 2048),
    "plc": FileType("application/vnd.mobius.plc", "application", 2048),
    "plf": FileType("application/vnd.pocketlearn", "application", 2048),
    "pls": FileType("application/pls+xml", "application", 2048),
    "pml": FileType("application/vnd.ctc-posml", "application", 2048),
    "png": FileType("image/png", "image", 256),
    "pnm": FileType("image/x-portable-anymap", "image", 256),
    "pnt": FileType("image/x-macpaint", "image", 256),
    "pntg": FileType("image/x-macpaint", "image", 256),
    "portpkg": FileType("application/vnd.macports.portpkg", "application", 2048),
    "pot": FileType("application/vnd.ms-powerpoint", "application", 2048),
    "potm": FileType("application/vnd.ms-powerpoint.template.macroenabled.12", "application", 2048),
    "potx": FileType("application/vnd.openxmlformats-officedocument.presentationml.template", "application", 2048),
    "ppam": FileType("application/vnd.ms-powerpoint.addin.macroenabled.12", "application", 2048),
    "ppd": FileType("application/vnd.cups-ppd", "application", 2048),
    "ppm": FileType("image/x-portable-pixmap", "image", 256),
    "pps": FileType("application/vnd.ms-powerpoint", "application", 2048),
    "ppsm": FileType("application/vnd.ms-powerpoint.slideshow.macroenabled.12", "application", 2048),
    "ppsx": FileType("application/vnd.openxmlformats-officedocument.presentationml.slideshow", "application", 2048),
    "ppt": FileType("application/vnd.ms-powerpoint", "application", 2048),
    "pptm": FileType("application/vnd.ms-powerpoint.presentation.macroenabled.12", "application", 2048),
    "pptx": FileType("application/vnd.openxmlformats-officedocument.presentationml.presentation", "application", 2048),
    "pqa": FileType("application/vnd.palm", "application", 2048),
    "prc": FileType("application/x-mobipocket-ebook", "application", 2048),
    "pre": FileType("application/vnd.lotus-freelance", "application", 2048),
    "prf": FileType("application/pics-rules", "application", 2048),
    "ps": FileType("application/postscript", "application", 2048),
    "psb": FileType("application/vnd.3gpp.pic-bw-small", "application", 2048),
    "psd": FileType("image/vnd.adobe.photoshop", "image", 256),
    "psf": FileType("application/x-font-linux-psf", "application", 2048),
    "pskcxml": FileType("application/pskc+xml", "application", 2048),
    "ptid": FileType("application/vnd.pvi.ptid1", "application", 2048),
    "pub": FileType("application/x-mspublisher", "application", 2048),
    "pvb": FileType("application/vnd.3gpp.pic-bw-var", "application", 2048),
    "pwn": FileType("application/vnd.3m.post-it-notes", "application", 2048),
    "pya": FileType("audio/vnd.ms-playready.media.pya", "audio", 1024),
    "pyv": FileType("video/vnd.ms-playready.media.pyv", "video", 4096),
    "qam": FileType("application/vnd.epson.quickanime", "application", 2048),
    "qbo": FileType("application/vnd.intu.qbo", "application", 2048),
    "qfx": FileType("application/vnd.intu.qfx", "application", 2048),
    "qps": FileType("application/vnd.publishare-delta-tree", "application", 2048),
    "qt": FileType("video/quicktime", "video", 4096),
    "qti": FileType("image/x-quicktime", "image", 256),
    "qtif": FileType("image/x-quicktime", "image", 256),
    "qwd": FileType("application/vnd.quark.quarkxpress", "application", 2048),
    "qwt": FileType("application/vnd.quark.quarkxpress", "application", 2048),
    "qxb": FileType("application/vnd.quark.quarkxpress", "application", 2048),
    "qxd": FileType("application/vnd.quark.quarkxpress", "application", 2048),
    "qxl": FileType("application/vnd.quark.quarkxpress", "application", 2048),
    "qxt": FileType("application/vnd.quark.quarkxpress", "application", 2048),
    "ra": FileType("audio/x-pn-realaudio", "audio", 1024),
    "ram": FileType("audio/x-pn-realaudio", "audio", 1024),
    "rar": FileType("application/x-rar-compressed", "application", 2048),
    "ras": FileType("image/x-cmu-raster", "image", 256),
    "rcprofile": FileType("application/vnd.ipunplugged.rcprofile", "application", 2048),
    "rdf": FileType("application/rdf+xml", "application", 2048),
    "rdz": FileType("application/vnd.data-vision.rdz", "application", 2048),
    "rep": FileType("application/vnd.businessobjects", "application", 2048),
    "res": FileType("application/x-dtbresource+xml", "application", 2048),
    "rgb": FileType("image/x-rgb", "image", 256),
    "rif": FileType("application/reginfo+xml", "application", 2048),
    "rip": FileType("audio/vnd.rip", "audio", 1024),
    "ris": FileType("application/x-research-info-systems", "application", 2048),
    "rl": FileType("application/resource-lists+xml", "application", 2048),
    "rlc": FileType("image/vnd.fujixerox.edmics-rlc", "image", 256),
    "rld": FileType("application/resource-lists-diff+xml", "application", 2048),
    "rm": FileType("application/vnd.rn-realmedia", "application", 2048),
    "rmi": FileType("audio/midi", "audio", 1024),
    "rmp": FileType("audio/x-pn-realaudio-plugin", "audio", 1024),
    "rms": FileType("application/vnd.jcp.javame.midlet-rms", "application", 2048),
    "rmvb": FileType("application/vnd.rn-realmedia-vbr", "application", 2048),
    "rnc": FileType("application/relax-ng-compact-syntax", "application", 2048),
    "roa": FileType("application/rpki-roa", "application", 2048),
    "roff": FileType("text/troff", "text", 64),
    "rp9": FileType("application/vnd.cloanto.rp9", "application", 2048),
    "rpss": FileType("application/vnd.nokia.radio-presets", "application", 2048),
    "rpst": FileType("application/vnd.nokia.radio-preset", "application", 2048),
    "rq": FileType("application/sparql-query", "application", 2048),
    "rs": FileType("application/rls-services+xml", "application", 2048),
    "rsd": FileType("application/rsd+xml", "application", 2048),
    "rss": FileType("application/rss+xml", "application", 2048),
    "rtf": FileType("application/rtf", "application", 2048),
    "rtx": FileType("text/richtext", "text", 64),
    "s": FileType("text/x-asm", "text", 64),
    "s3m": FileType("audio/s3m", "audio", 1024),
    "saf": FileType("application/vnd.yamaha.smaf-audio", "application", 2048),
    "sbml": FileType("application/sbml+xml", "application", 2048),
    "sc": FileType("application/vnd.ibm.secure-container", "application", 2048),
    "scd": FileType("application/x-msschedule", "application", 2048),
    "scm": FileType("application/vnd.lotus-screencam", "application", 2048),
    "scq": FileType("application/scvp-cv-request", "application", 2048),
    "scs": FileType("application/scvp-cv-response", "application", 2048),
    "scurl": FileType("text/vnd.curl.scurl", "text", 64),
    "sda": FileType("application/vnd.stardivision.draw", "application", 2048),
    "sdc": FileType("application/vnd.stardivision.calc", "application", 2048),
    "sdd": FileType("application/vnd.stardivision.impress", "application", 2048),
    "sdkd": FileType("application/vnd.solent.sdkm+xml", "application", 2048),
    "sdkm": FileType("application/vnd.solent.sdkm+xml", "application", 2048),
    "sdp": FileType("application/sdp", "application", 2048),
    "sdw": FileType("application/vnd.stardivision.writer", "application", 2048),
    "see": FileType("application/vnd.seemail", "application", 2048),
    "seed": FileType("application/vnd.fdsn.seed", "application", 2048),
    "sema": FileType("application/vnd.sema", "application", 2048),
    "semd": FileType("application/vnd.semd", "application", 2048),
    "semf": FileType("application/vnd.semf", "application", 2048),
    "ser": FileType("application/java-serialized-object", "application", 2048),
    "setpay": FileType("application/set-payment-initiation", "application", 2048),
    "setreg": FileType("application/set-registration-initiation", "application", 2048),
    "sfd-hdstx": FileType("application/vnd.hydrostatix.sof-data", "application", 2048),
    "sfs": FileType("application/vnd.spotfire.sfs", "application", 2048),
    "sfv": FileType("text/x-sfv", "text", 64),
    "sgi": FileType("image/sgi", "image", 256),
    "sgl": FileType("application/vnd.stardivision.writer-global", "application", 2048),
    "sgm": FileType("text/sgml", "text", 64),
    "sgml": FileType("text/sgml", "text", 64),
    "sh": FileType("application/x-sh", "application", 2048),
    "shar": FileType("application/x-shar", "application", 2048),
    "shf": FileType("application/shf+xml", "application", 2048),
    "sid": FileType("image/x-mrsid-image", "image", 256),
    "sig": FileType("application/pgp-signature", "application", 2048),
    "sil": FileType("audio/silk", "audio", 1024),
    "silo": FileType("model/mesh", "model", 512),
    "sis": FileType("application/vnd.symbian.install", "application", 2048),
    "sisx": FileType("application/vnd.symbian.install", "application", 2048),
    "sit": FileType("application/x-stuffit", "application", 2048),
    "sitx": FileType("application/x-stuffitx", "application", 2048),
    "skd": FileType("application/vnd.koan", "application", 2048),
    "skm": FileType("application/vnd.koan", "application", 2048),
    "skp": FileType("application/vnd.koan", "application", 2048),
    "skt": FileType("application/vnd.koan", "application", 2048),
    "sldm": FileType("application/vnd.ms-powerpoint.slide.macroenabled.12", "application", 2048),
    "sldx": FileType("application/vnd.openxmlformats-officedocument.presentationml.slide", "application", 2048),
    "slt": FileType("application/vnd.epson.salt", "application", 2048),
    "sm": FileType("application/vnd.stepmania.stepchart", "application", 2048),
    "smf": FileType("application/vnd.stardivision.math", "application", 2048),
    "smi": FileType("application/smil+xml", "application", 2048),
    "smil": FileType("application/smil+xml", "application", 2048),
    "smv": FileType("video/x-smv", "video", 4096),
    "smzip": FileType("application/vnd.stepmania.package", "application", 2048),
    "snd": FileType("audio/basic", "audio", 1024),
    "snf": FileType("application/x-font-snf", "application", 2048),
    "so": FileType("application/octet-stream", "application", 2048),
    "spc": FileType("application/x-pkcs7-certificates", "application", 2048),
    "spf": FileType("application/vnd.yamaha.smaf-phrase", "application", 2048),
    "spl": FileType("application/x-futuresplash", "application", 2048),
    "spot": FileType("text/vnd.in3d.spot", "text", 64),
    "spp": FileType("application/scvp-vp-response", "application", 2048),
    "spq": FileType("application/scvp-vp-request", "application", 2048),
    "spx": FileType("audio/ogg", "audio", 1024),
    "sql": FileType("application/x-sql", "application", 2048),
    "src": FileType("application/x-wais-source", "application", 2048),
    "srt": FileType("application/x-subrip", "application", 2048),
    "sru": FileType("application/sru+xml", "application", 2048),
    "srx": FileType("application/sparql-results+xml", "application", 2048),
    "ssdl": FileType("application/ssdl+xml", "application", 2048),
    "sse": FileType("application/vnd.kodak-descriptor", "application", 2048),
    "ssf": FileType("application/vnd.epson.ssf", "application", 2048),
    "ssml": FileType("application/ssml+xml", "application", 2048),
    "st": FileType("application/vnd.sailingtracker.track", "application", 2048),
    "stc": FileType("application/vnd.sun.xml.calc.template", "application", 2048),
    "std": FileType("application/vnd.sun.xml.draw.template", "application", 2048),
    "stf": FileType("application/vnd.wt.stf", "application", 2048),
    "sti": FileType("application/vnd.sun.xml.impress.template", "application", 2048),
    "stk": FileType("application/hyperstudio", "application", 2048),
    "stl": FileType("application/vnd.ms-pki.stl", "application", 2048),
    "str": FileType("application/vnd.pg.format", "application", 2048),
    "stw": FileType("application/vnd.sun.xml.writer.template", "application", 2048),
    "sub": FileType("image/vnd.dvb.subtitle", "image", 256),
    "sus": FileType("application/vnd.sus-calendar", "application", 2048),
    "susp": FileType("application/vnd.sus-calendar", "application", 2048),
    "sv4cpio": FileType("application/x-sv4cpio", "application", 2048),
    "sv4crc": FileType("application/x-sv4crc", "application", 2048),
    "svc": FileType("application/vnd.dvb.service", "application", 2048),
    "svd": FileType("application/vnd.svd", "application", 2048),
    "svg": FileType("image/svg+xml", "image", 256),
    "svgz": FileType("image/svg+xml", "image", 256),
    "swa": FileType("application/x-director", "application", 2048),
    "swf": FileType("application/x-shockwave-flash", "application", 2048),
    "swi": FileType("application/vnd.aristanetworks.swi", "application", 2048),
    "sxc": FileType("application/vnd.sun.xml.calc", "application", 2048),
    "sxd": FileType("application/vnd.sun.xml.draw", "application", 2048),
    "sxg": FileType("application/vnd.sun.xml.writer.global", "application", 2048),
    "sxi": FileType("application/vnd.sun.xml.impress", "application", 2048),
    "sxm": FileType("application/vnd.sun.xml.math", "application", 2048),
    "sxw": FileType("application/vnd.sun.xml.writer", "application", 2048),
    "t": FileType("text/troff", "text", 64),
    "t3": FileType("application/x-t3vm-image", "application", 2048),
    "taglet": FileType("application/vnd.mynfc", "application", 2048),
    "tao": FileType("application/vnd.tao.intent-module-archive", "application", 2048),
    "tar": FileType("application/x-tar", "application", 2048),
    "tcap": FileType("application/vnd.3gpp2.tcap", "application", 2048),
    "tcl": FileType("application/x-tcl", "application", 2048),
    "teacher": FileType("application/vnd.smart.teacher", "application", 2048),
    "tei": FileType("application/tei+xml", "application", 2048),
    "teicorpus": FileType("application/tei+xml", "application", 2048),
    "tex": FileType("application/x-tex", "application", 2048),
    "texi": FileType("application/x-texinfo", "application", 2048),
    "texinfo": FileType("application/x-texinfo", "application", 2048),
    "text": FileType("text/plain", "text", 64),
    "tfi": FileType("application/thraud+xml", "application", 2048),
    "tfm": FileType("application/x-tex-tfm", "application", 2048),
    "tga": FileType("image/x-tga", "image", 256),
    "thmx": FileType("application/vnd.ms-officetheme", "application", 2048),
    "tif": FileType("image/tiff", "image", 256),
    "tiff": FileType("image/tiff", "image", 256),
    "tmo": FileType("application/vnd.tmobile-livetv", "application", 2048),
    "torrent": FileType("application/x-bittorrent", "application", 2048),
    "tpl": FileType("application/vnd.groove-tool-template", "application", 2048),
    "tpt": FileType("application/vnd.trid.tpt", "application", 2048),
    "tr": FileType("text/troff", "text", 64),
    "tra": FileType("application/vnd.trueapp", "application", 2048),
    "trm": FileType("application/x-msterminal", "application", 2048),
    "ts": FileType("video/mp2t", "video", 4096),
    "tsd": FileType("application/timestamped-data", "application", 2048),
    "tsv": FileType("text/tab-separated-values", "text", 64),
    "ttc": FileType("font/collection", "font", 64),
    "ttf": FileType("font/ttf", "font", 64),
    "ttl": FileType("text/turtle", "text", 64),
    "twd": FileType("application/vnd.simtech-mindmapper", "application", 2048),
    "twds": FileType("application/vnd.simtech-mindmapper", "application", 2048),
    "txd": FileType("application/vnd.genomatix.tuxedo", "application", 2048),
    "txf": FileType("application/vnd.mobius.txf", "application", 2048),
    "txt": FileType("text/plain", "text", 64),
    "u32": FileType("application/x-authorware-bin", "application", 2048),
    "udeb": FileType("application/x-debian-package", "application", 2048),
    "ufd": FileType("application/vnd.ufdl", "application", 2048),
    "ufdl": FileType("application/vnd.ufdl", "application", 2048),
    "ulx": FileType("application/x-glulx", "application", 2048),
    "umj": FileType("application/vnd.umajin", "application", 2048),
    "unityweb": FileType("application/vnd.unity", "application", 2048),
    "uoml": FileType("application/vnd.uoml+xml", "application", 2048),
    "uri": FileType("text/uri-list", "text", 64),
    "uris": FileType("text/uri-list", "text", 64),
    "urls": FileType("text/uri-list", "text", 64),
    "ustar": FileType("application/x-ustar", "application", 2048),
    "utz": FileType("application/vnd.uiq.theme", "application", 2048),
    "uu": FileType("text/x-uuencode", "text", 64),
    "uva": FileType("audio/vnd.dece.audio", "audio", 1024),
    "uvd": FileType("application/vnd.dece.data", "application", 2048),
    "uvf": FileType("application/vnd.dece.data", "application", 2048),
    "uvg": FileType("image/vnd.dece.graphic", "image", 256),
    "uvh": FileType("video/vnd.dece.hd", "video", 4096),
    "uvi": FileType("image/vnd.dece.graphic", "image", 256),
    "uvm": FileType("video/vnd.dece.mobile", "video", 4096),
    "uvp": FileType("video/vnd.dece.pd", "video", 4096),
    "uvs": FileType("video/vnd.dece.sd", "video", 4096),
    "uvt": FileType("application/vnd.dece.ttml+xml", "application", 2048),
    "uvu": FileType("video/vnd.uvvu.mp4", "video", 4096),
    "uvv": FileType("video/vnd.dece.video", "video", 4096),
    "uvva": FileType("audio/vnd.dece.audio", "audio", 1024),
    "uvvd": FileType("application/vnd.dece.data", "application", 2048),
    "uvvf": FileType("application/vnd.dece.data", "application", 2048),
    "uvvg": FileType("image/vnd.dece.graphic", "image", 256),
    "uvvh": FileType("video/vnd.dece.hd", "video", 4096),
    "uvvi": FileType("image/vnd.dece.graphic", "image", 256),
    "uvvm": FileType("video/vnd.dece.mobile", "video", 4096),
    "uvvp": FileType("video/vnd.dece.pd", "video", 4096),
    "uvvs": FileType("video/vnd.dece.sd", "video", 4096),
    "uvvt": FileType("application/vnd.dece.ttml+xml", "application", 2048),
    "uvvu": FileType("video/vnd.uvvu.mp4", "video", 4096),
    "uvvv": FileType("video/vnd.dece.video", "video", 4096),
    "uvvx": FileType("application/vnd.dece.unspecified", "application", 2048),
    "uvvz": FileType("application/vnd.dece.zip", "application", 2048),
    "uvx": FileType("application/vnd.dece.unspecified", "application", 2048),
    "uvz": FileType("application/vnd.dece.zip", "application", 2048),
    "vcard": FileType("text/vcard", "text", 64),
    "vcd": FileType("application/x-cdlink", "application", 2048),
    "vcf": FileType("text/x-vcard", "text", 64),
    "vcg": FileType("application/vnd.groove-vcard", "application", 2048),
    "vcs": FileType("text/x-vcalendar", "text", 64),
    "vcx": FileType("application/vnd.vcx", "application", 2048),
    "vis": FileType("application/vnd.visionary", "application", 2048),
    "viv": FileType("video/vnd.vivo", "video", 4096),
    "vob": FileType("video/x-ms-vob", "video", 4096),
    "vor": FileType("application/vnd.stardivision.writer", "application", 2048),
    "vox": FileType("application/x-authorware-bin", "application", 2048),
    "vrml": FileType("model/vrml", "model", 512),
    "vsd": FileType("application/vnd.visio", "application", 2048),
    "vsf": FileType("application/vnd.vsf", "application", 2048),
    "vss": FileType("application/vnd.visio", "application", 2048),
    "vst": FileType("application/vnd.visio", "application", 2048),
    "vsw": FileType("application/vnd.visio", "application", 2048),
    "vtu": FileType("model/vnd.vtu", "model", 512),
    "vxml": FileType("application/voicexml+xml", "application", 2048),
    "w3d": FileType("application/x-director", "application", 2048),
    "wad": FileType("application/x-doom", "application", 2048),
    "wasm": FileType("application/wasm", "application", 2048),
    "wav": FileType("audio/x-wav", "audio", 1024),
    "wax": FileType("audio/x-ms-wax", "audio", 1024),
    "wbmp": FileType("image/vnd.wap.wbmp", "image", 256),
    "wbs": FileType("application/vnd.criticaltools.wbs+xml", "application", 2048),
    "wbxml": FileType("application/vnd.wap.wbxml", "application", 2048),
    "wcm": FileType("application/vnd.ms-works", "application", 2048),
    "wdb": FileType("application/vnd.ms-works", "application", 2048),
    "wdp": FileType("image/vnd.ms-photo", "image", 256),
    "weba": FileType("audio/webm", "audio", 1024),
    "webm": FileType("video/webm", "video", 4096),
    "webp": FileType("image/webp", "image", 256),
    "wg": FileType("application/vnd.pmi.widget", "application", 2048),
    "wgt": FileType("application/widget", "application", 2048),
    "wks": FileType("application/vnd.ms-works", "application", 2048),
    "wm": FileType("video/x-ms-wm", "video", 4096),
    "wma": FileType("audio/x-ms-wma", "audio", 1024),
    "wmd": FileType("application/x-ms-wmd", "application", 2048),
    "wmf": FileType("application/x-msmetafile", "application", 2048),
    "wml": FileType("text/vnd.wap.wml", "text", 64),
    "wmlc": FileType("application/vnd.wap.wmlc", "application", 2048),
    "wmls": FileType("text/vnd.wap.wmlscript", "text", 64),
    "wmlsc": FileType("application/vnd.wap.wmlscriptc", "application", 2048),
    "wmv": FileType("video/x-ms-wmv", "video", 4096),
    "wmx": FileType("video/x-ms-wmx", "video", 4096),
    "wmz": FileType("application/x-ms-wmz", "application", 2048),
    "woff": FileType("font/woff", "font", 64),
    "woff2": FileType("font/woff2", "font", 64),
    "wpd": FileType("application/vnd.wordperfect", "application", 2048),
    "wpl": FileType("application/vnd.ms-wpl", "application", 2048),
    "wps": FileType("application/vnd.ms-works", "application", 2048),
    "wqd": FileType("application/vnd.wqd", "application", 2048),
    "wri": FileType("application/x-mswrite", "application", 2048),
    "wrl": FileType("model/vrml", "model", 512),
    "wsdl": FileType("application/wsdl+xml", "application", 2048),
    "wspolicy": FileType("application/wspolicy+xml", "application", 2048),
    "wtb": FileType("application/vnd.webturbo", "application", 2048),
    "wvx": FileType("video/x-ms-wvx", "video", 4096),
    "x32": FileType("application/x-authorware-bin", "application", 2048),
    "x3d": FileType("model/x3d+xml", "model", 512),
    "x3db": FileType("model/x3d+binary", "model", 512),
    "x3dbz": FileType("model/x3d+binary", "model", 512),
    "x3dv": FileType("model/x3d+vrml", "model", 512),
    "x3dvz": FileType("model/x3d+vrml", "model", 512),
    "x3dz": FileType("model/x3d+xml", "model", 512),
    "xaml": FileType("application/xaml+xml", "application", 2048),
    "xap": FileType("application/x-silverlight-app", "application", 2048),
    "xar": FileType("application/vnd.xara", "application", 2048),
    "xbap": FileType("application/x-ms-xbap", "application", 2048),
    "xbd": FileType("application/vnd.fujixerox.docuworks.binder", "application", 2048),
    "xbm": FileType("image/x-xbitmap", "image", 256),
    "xdf": FileType("application/xcap-diff+xml", "application", 2048),
    "xdm": FileType("application/vnd.syncml.dm+xml", "application", 2048),
    "xdp": FileType("application/vnd.adobe.xdp+xml", "application", 2048),
    "xdssc": FileType("application/dssc+xml", "application", 2048),
    "xdw": FileType("application/vnd.fujixerox.docuworks", "application", 2048),
    "xenc": FileType("application/xenc+xml", "application", 2048),
    "xer": FileType("application/patch-ops-error+xml", "application", 2048),
    "xfdf": FileType("application/vnd.adobe.xfdf", "application", 2048),
    "xfdl": FileType("application/vnd.xfdl", "application", 2048),
    "xht": FileType("application/xhtml+xml", "application", 2048),
    "xhtml": FileType("application/xhtml+xml", "application", 2048),
    "xhvml": FileType("application/xv+xml", "application", 2048),
    "xif": FileType("image/vnd.xiff", "image", 256),
    "xla": FileType("application/vnd.ms-excel", "application", 2048),
    "xlam": FileType("application/vnd.ms-excel.addin.macroenabled.12", "application", 2048),
    "xlc": FileType("application/vnd.ms-excel", "application", 2048),
    "xlf": FileType("application/x-xliff+xml", "application", 2048),
    "xlm": FileType("application/vnd.ms-excel", "application", 2048),
    "xls": FileType("application/vnd.ms-excel", "application", 2048),
    "xlsb": FileType("application/vnd.ms-excel.sheet.binary.macroenabled.12", "application", 2048),
    "xlsm": FileType("application/vnd.ms-excel.sheet.macroenabled.12", "application", 2048),
    "xlsx": FileType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application", 2048),
    "xlt": FileType("application/vnd.ms-excel", "application", 2048),
    "xltm": FileType("application/vnd.ms-excel.template.macroenabled.12", "application", 2048),
    "xltx": FileType("application/vnd.openxmlformats-officedocument.spreadsheetml.template", "application", 2048),
    "xlw": FileType("application/vnd.ms-excel", "application", 2048),
    "xm": FileType("audio/xm", "audio", 1024),
    "xml": FileType("application/xml", "application", 2048),
    "xo": FileType("application/vnd.olpc-sugar", "application", 2048),
    "xop": FileType("application/xop+xml", "application", 2048),
    "xpi": FileType("application/x-xpinstall", "application", 2048),
    "xpl": FileType("application/xproc+xml", "application", 2048),
    "xpm": FileType("image/x-xpixmap", "image", 256),
    "xpr": FileType("application/vnd.is-xpr", "application", 2048),
    "xps": FileType("application/vnd.ms-xpsdocument", "application", 2048),
    "xpw": FileType("application/vnd.intercon.formnet", "application", 2048),
    "xpx": FileType("application/vnd.intercon.formnet", "application", 2048),
    "xsl": FileType("application/xml", "application", 2048),
    "xslt": FileType("application/xslt+xml", "application", 2048),
    "xsm": FileType("application/vnd.syncml+xml", "application", 2048),
    "xspf": FileType("application/xspf+xml", "application", 2048),
    "xul": FileType("application/vnd.mozilla.xul+xml", "application", 2048),
    "xvm": FileType("application/xv+xml", "application", 2048),
    "xvml": FileType("application/xv+xml", "application", 2048),
    "xwd": FileType("image/x-xwindowdump", "image", 256),
    "xyz": FileType("chemical/x-xyz", "chemical", 64),
    "xz": FileType("application/x-xz", "application", 2048),
    "yang": FileType("application/yang", "application", 2048),
    "yin": FileType("application/yin+xml", "application", 2048),
    "z1": FileType("application/x-zmachine", "application", 2048),
    "z2": FileType("application/x-zmachine", "application", 2048),
    "z3": FileType("application/x-zmachine", "application", 2048),
    "z4": FileType("application/x-zmachine", "application", 2048),
    "z5": FileType("application/x-zmachine", "application", 2048),
    "z6": FileType("application/x-zmachine", "application", 2048),
    "z7": FileType("application/x-zmachine", "application", 2048),
    "z8": FileType("application/x-zmachine", "application", 2048),
    "zaz": FileType("application/vnd.zzazz.deck+xml", "application", 2048),
    "zip": FileType("application/zip", "application", 2048),
    "zir": FileType("application/vnd.zul", "application", 2048),
    "zirz": FileType("application/vnd.zul", "application", 2048),
    "zmm": FileType("application/vnd.handheld-entertainment+xml", "application", 2048),
}


def error_response(status: int, message: str) -> Response:
    return Response(status=status, payload={"status": "error", "message": message})


def ok_response(**payload) -> Response:
    return Response(status=200, payload={"status": "ok", **payload})


class FileManager:
    """Checks and filesystem helpers for files entering the service."""

    @staticmethod
    def validate_file_extension(file_name: str) -> bool:
        """True when the file name ends in an extension the service accepts."""
        _, extension = os.path.splitext(file_name)
        return extension.lstrip(".").lower() in FILE_TYPES

    @staticmethod
    def is_safe_file_name(file_name: str) -> bool:
        """True when the name is a bare file name with no folder part."""
        if file_name in ("", ".", ".."):
            return False
        return os.path.basename(file_name) == file_name and "\\" not in file_name

    @staticmethod
    def max_bytes_for(file_name: str) -> int:
        """The largest upload allowed for this file name."""
        _, extension = os.path.splitext(file_name)
        file_type = FILE_TYPES.get(extension.lstrip(".").lower())
        if file_type is None:
            return 0
        return file_type.max_mb * 1024 * 1024

    @staticmethod
    def media_type_for(file_name: str) -> str:
        """The media type recorded for this file name."""
        _, extension = os.path.splitext(file_name)
        file_type = FILE_TYPES.get(extension.lstrip(".").lower())
        return file_type.mime if file_type else "application/octet-stream"

    @staticmethod
    def save_uploaded_file(root: str, transfer_id: str, uploaded: UploadedFile) -> str:
        """Write a single-request upload to its final path and return that path."""
        directory = os.path.join(root, transfer_id)
        os.makedirs(directory, exist_ok=True)
        final_path = os.path.join(directory, os.path.basename(uploaded.name))
        temp_path = f"{final_path}.tmp"
        with open(temp_path, "wb") as handle:
            handle.write(uploaded.content)
        os.replace(temp_path, final_path)
        return final_path


class ChunkManager:
    """Stores the chunks of one transfer under ``<root>/<transfer_id>/``."""

    def __init__(self, root: str, transfer_id: str):
        self.directory = os.path.join(root, transfer_id)

    def write(self, offset: int, chunk: bytes) -> None:
        """Store one chunk under a name that sorts by its offset."""
        os.makedirs(self.directory, exist_ok=True)
        path = os.path.join(self.directory, f"{offset:020d}.part")
        temp_path = f"{path}.tmp"
        with open(temp_path, "wb") as handle:
            handle.write(chunk)
        os.replace(temp_path, path)

    def chunk_names(self) -> list[str]:
        """The stored chunks in offset order."""
        if not os.path.isdir(self.directory):
            return []
        return sorted(
            name for name in os.listdir(self.directory) if name.endswith(".part")
        )

    def received_bytes(self) -> int:
        """Total size of the stored chunks."""
        return sum(
            os.path.getsize(os.path.join(self.directory, name))
            for name in self.chunk_names()
        )

    def combine(self, upload_name: str) -> str:
        """Join the chunks into the final file and remove them."""
        final_path = os.path.realpath(os.path.join(self.directory, upload_name))
        if os.path.dirname(final_path) != os.path.realpath(self.directory):
            raise ValueError(f"Upload name escapes the transfer dir: {upload_name!r}")
        names = self.chunk_names()
        temp_path = f"{final_path}.tmp"
        with open(temp_path, "wb") as combined:
            for name in names:
                with open(os.path.join(self.directory, name), "rb") as part:
                    shutil.copyfileobj(part, combined)
        os.replace(temp_path, final_path)
        for name in names:
            os.remove(os.path.join(self.directory, name))
        return final_path

    def discard(self) -> None:
        """Remove everything stored for this transfer."""
        shutil.rmtree(self.directory, ignore_errors=True)


@dataclass
class Transfer:
    """One upload, from creation until it is complete or cancelled."""

    id: str
    owner: str
    length: int
    received: int = 0
    state: str = "uploading"
    final_path: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    tags: frozenset[str] = frozenset()
    region: Optional[str] = None


class TransferStore:
    """Thread-safe in-memory store. Production swaps in the database version."""

    def __init__(self):
        self._lock = threading.Lock()
        self._transfers: dict[str, Transfer] = {}

    def create(self, owner: str, length: int) -> Transfer:
        transfer = Transfer(id=uuid.uuid4().hex, owner=owner, length=length)
        with self._lock:
            self._transfers[transfer.id] = transfer
        return transfer

    def get(self, transfer_id: str) -> Optional[Transfer]:
        with self._lock:
            return self._transfers.get(transfer_id)

    def for_owner(self, owner: str) -> list[Transfer]:
        with self._lock:
            found = [t for t in self._transfers.values() if t.owner == owner]
        return sorted(found, key=lambda transfer: transfer.created_at)

    def finished(self) -> list[Transfer]:
        with self._lock:
            return [t for t in self._transfers.values() if t.state == "complete"]

    def delete(self, transfer_id: str) -> None:
        with self._lock:
            self._transfers.pop(transfer_id, None)


class QuotaService:
    """Tracks how many bytes each owner has reserved."""

    def __init__(self, limit_bytes: int = DEFAULT_QUOTA_BYTES):
        self.limit_bytes = limit_bytes
        self._lock = threading.Lock()
        self._used: dict[str, int] = {}

    def reserve(self, owner: str, size: int) -> bool:
        """Reserve bytes for an owner. False when that would pass the limit."""
        with self._lock:
            used = self._used.get(owner, 0)
            if used + size > self.limit_bytes:
                return False
            self._used[owner] = used + size
            return True

    def release(self, owner: str, size: int) -> None:
        with self._lock:
            self._used[owner] = max(0, self._used.get(owner, 0) - size)

    def used(self, owner: str) -> int:
        with self._lock:
            return self._used.get(owner, 0)


class AuditTrail:
    """Append-only record of what happened to each transfer."""

    def __init__(self):
        self._lock = threading.Lock()
        self.events: list[dict] = []

    def record(self, transfer_id: str, action: str, **details) -> None:
        with self._lock:
            self.events.append(
                {
                    "transfer_id": transfer_id,
                    "action": action,
                    "at": time.time(),
                    **details,
                }
            )

    def for_transfer(self, transfer_id: str) -> list[dict]:
        with self._lock:
            return [e for e in self.events if e["transfer_id"] == transfer_id]


@dataclass
class Dependencies:
    """Everything a handler needs from the rest of the service."""

    root: str
    transfers: TransferStore = field(default_factory=TransferStore)
    quotas: QuotaService = field(default_factory=QuotaService)
    audit: AuditTrail = field(default_factory=AuditTrail)


def describe_transfer(transfer: Transfer) -> dict:
    """The public view of a transfer."""
    return {
        "id": transfer.id,
        "state": transfer.state,
        "received": transfer.received,
        "length": transfer.length,
    }


def handle_create_transfer(request: Request, deps: Dependencies) -> Response:
    """Start a resumable upload and return its id."""
    owner = request.headers.get("X-Owner")
    if not owner:
        return error_response(401, "An owner is required.")
    try:
        length = int(request.headers.get("Upload-Length", ""))
    except ValueError:
        return error_response(400, "Upload-Length must be an integer.")
    if length <= 0:
        return error_response(400, "Upload-Length must be positive.")
    try:
        region = resolve_region(request.headers.get("Upload-Region"))
    except UnknownRegion:
        return error_response(400, "Unknown storage region.")
    transfer = deps.transfers.create(owner, length)
    transfer.region = region
    deps.audit.record(transfer.id, "created", owner=owner, length=length)
    return ok_response(transfer=describe_transfer(transfer))


def handle_transfer_status(transfer_id: str, deps: Dependencies) -> Response:
    """Report how far an upload has got."""
    transfer = deps.transfers.get(transfer_id)
    if transfer is None:
        return error_response(404, "Unknown transfer.")
    return ok_response(transfer=describe_transfer(transfer))


def handle_cancel_transfer(transfer_id: str, deps: Dependencies) -> Response:
    """Cancel an upload, remove its chunks and give back its quota."""
    transfer = deps.transfers.get(transfer_id)
    if transfer is None:
        return error_response(404, "Unknown transfer.")
    if transfer.state in TERMINAL_STATES:
        return error_response(409, f"Transfer is already {transfer.state}.")
    ChunkManager(deps.root, transfer.id).discard()
    deps.quotas.release(transfer.owner, transfer.received)
    transfer.state = "cancelled"
    deps.audit.record(transfer.id, "cancelled")
    return ok_response(transfer=describe_transfer(transfer))


def handle_list_transfers(request: Request, deps: Dependencies) -> Response:
    """List the caller's uploads, oldest first."""
    owner = request.headers.get("X-Owner")
    if not owner:
        return error_response(401, "An owner is required.")
    return ok_response(
        transfers=[describe_transfer(t) for t in deps.transfers.for_owner(owner)]
    )


def handle_multipart_upload(request: Request, deps: Dependencies) -> Response:
    """Store a file that arrived in one multipart request."""
    owner = request.headers.get("X-Owner")
    if not owner:
        return error_response(401, "An owner is required.")
    uploaded = request.files.get("file")
    if uploaded is None:
        return error_response(400, "A file part is required.")
    size = len(uploaded.content)
    if size > MAX_SINGLE_REQUEST_BYTES:
        return error_response(413, "Use a resumable upload for files this large.")
    if not deps.quotas.reserve(owner, size):
        return error_response(507, "Storage quota exceeded.")
    transfer = deps.transfers.create(owner, size)
    transfer.final_path = FileManager.save_uploaded_file(
        deps.root, transfer.id, uploaded
    )
    transfer.received = size
    transfer.state = "complete"
    transfer.completed_at = time.time()
    deps.audit.record(transfer.id, "uploaded", owner=owner, size=size)
    return ok_response(transfer=describe_transfer(transfer))


def handle_chunk_patch(
    request: Request, transfer_id: str, deps: Dependencies
) -> Response:
    """Apply one chunk of a resumable upload."""
    missing = [
        name for name in REQUIRED_CHUNK_HEADERS if not request.headers.get(name)
    ]
    if missing:
        return error_response(400, f"Missing required headers: {', '.join(missing)}")

    if not TRANSFER_ID_PATTERN.fullmatch(transfer_id or ""):
        return error_response(400, "Invalid transfer id.")

    try:
        offset = int(request.headers.get("Upload-Offset"))
        length = int(request.headers.get("Upload-Length"))
    except ValueError:
        return error_response(
            400, "Upload-Offset and Upload-Length must be integers."
        )
    if offset < 0:
        return error_response(400, "Upload-Offset must not be negative.")
    if length <= 0:
        return error_response(400, "Upload-Length must be positive.")

    transfer = deps.transfers.get(transfer_id)
    if transfer is None:
        return error_response(404, "Unknown transfer.")
    if transfer.state in TERMINAL_STATES:
        return error_response(409, f"Transfer is already {transfer.state}.")
    if transfer.length != length:
        return error_response(409, "Upload-Length does not match this transfer.")
    if transfer.received != offset:
        return error_response(
            409, f"Expected Upload-Offset {transfer.received}, got {offset}."
        )
    if request.headers.get("X-Owner") != transfer.owner:
        return error_response(403, "This transfer belongs to another owner.")
    if time.time() - transfer.created_at > UPLOAD_EXPIRY_SECONDS:
        transfer.state = "expired"
        deps.audit.record(transfer_id, "expired")
        return error_response(410, "This upload has expired.")

    content_type = request.headers.get("Content-Type", CHUNK_CONTENT_TYPE)
    if content_type != CHUNK_CONTENT_TYPE:
        return error_response(415, f"Chunks must be sent as {CHUNK_CONTENT_TYPE}.")

    chunk = request.body
    if not chunk:
        return error_response(400, "A chunk cannot be empty.")
    if len(chunk) > MAX_CHUNK_BYTES:
        return error_response(413, "Chunk is larger than the chunk limit.")
    if offset + len(chunk) > length:
        return error_response(400, "Chunk runs past Upload-Length.")

    expected_digest = request.headers.get("Upload-Checksum")
    if expected_digest:
        actual_digest = hashlib.sha256(chunk).hexdigest()
        if not hmac.compare_digest(actual_digest, expected_digest.lower()):
            deps.audit.record(transfer_id, "checksum_mismatch", offset=offset)
            return error_response(422, "Chunk failed its checksum.")

    if not deps.quotas.reserve(transfer.owner, len(chunk)):
        return error_response(507, "Storage quota exceeded.")

    chunks = ChunkManager(deps.root, transfer_id)
    chunks.write(offset, chunk)
    transfer.received += len(chunk)
    deps.audit.record(transfer_id, "chunk", offset=offset, size=len(chunk))

    if transfer.received == length:
        transfer.final_path = chunks.combine(request.headers.get("Upload-Name"))
        transfer.state = "complete"
        transfer.completed_at = time.time()
        deps.audit.record(transfer_id, "completed", path=transfer.final_path)
    return ok_response(transfer=describe_transfer(transfer))
