"""
© Copyright 2020 HP Development Company, L.P.
SPDX-License-Identifier: GPL-2.0-only
"""

from mlgit import log
from mlgit.utils import json_load, ensure_path_exists
from cid import CIDv0, make_cid, CIDv1
import multihash
import hashlib
import os
import json

'''implementation of a "hashdir" based filesystem
Lack a few desirable properties of MultihashFS.
 
Although good enough for ml-git cache implementation.'''
class HashFS(object):
	def __init__(self, path, blocksize = 256*1024, levels=2):
		self._blk_size = blocksize
		if blocksize < 64*1024: self._blk_size = 64*1024
		if blocksize > 1024*1024: self._blk_size = 1024*1024

		self._levels = levels
		if levels < 1: self._levels = 1
		if levels > 16: self.levels = 16

		self._path = os.path.join(path, "hashfs")
		ensure_path_exists(self._path)
		self._logpath = os.path.join(self._path, "log")
		ensure_path_exists(self._logpath)

	def _hash_filename(self, filename):
		m = hashlib.md5()
		m.update(filename.encode())
		return m.hexdigest()

	def _get_hash(self, filename, start=0):
		hs = [filename[i:i + 2] for i in range(start, start+2 * (self._levels), 2)]
		h = os.sep.join(hs)
		return h

	def link(self, key, srcfile):
		dstkey = self._get_hashpath(key)
		ensure_path_exists(os.path.dirname(dstkey))

		if os.path.exists(dstkey) == True:
			log.debug("Cache: entry cache [%s] already exists for [%s]. possible duplicate." % (key, srcfile))
			os.unlink(srcfile)
			os.link(dstkey, srcfile)
			return

		log.info("Cache: creating entry cache [%s] for [%s]" % (key, srcfile))
		os.link(srcfile, dstkey)

	def _get_hashpath(self, filename):
		hfilename= self._hash_filename(filename)
		h = self._get_hash(hfilename)
		return os.path.join(self._path  , h, filename)

	def exists(self, filename):
		dstfile = self._get_hashpath(os.path.basename(filename))
		return os.path.exists(dstfile)

	def put(self, srcfile):
		dstfile = self._get_hashpath(os.path.basename(srcfile))
		ensure_path_exists(os.path.dirname(dstfile))
		os.link(srcfile, dstfile)
		self._log(dstfile)
		return os.path.basename(srcfile)

	def get(self, file, dstfile):
		srcfile = self._get_hashpath(file)
		os.link(srcfile, dstfile)
		st = os.stat(srcfile)
		return st.st_size

	def reset_log(self):
		log.debug("HashFS: update hashfs log")
		fullpath = os.path.join(self._logpath, "store.log")
		os.unlink(fullpath)

	def _log(self, objkey, links=[]):
		log.debug("HashFS: update log for key [%s]" % (objkey))
		fullpath = os.path.join(self._logpath, "store.log")
		with open(fullpath, "a") as f:
			f.write("%s\n" % (objkey))
			for link in links:
				h = link["Hash"]
				f.write("%s\n" % (h))

	'''walk implementation to make appear hashfs as a single namespace (and/or hide hashdir implementation details'''
	def walk(self, page_size=50):
		nfiles = []
		for root, dirs, files in os.walk(self._path):
			if 'store.log' in files: continue
			if len(files) > 0: nfiles.extend(files)
			if len(nfiles) >= page_size: yield nfiles
		if len(nfiles) > 0: yield nfiles

	'''Checks integrity of all files under HashFS'''
	def fsck(self, exclude=[]):
		return None

'''Implementation of a content-addressable filesystem
This filesystem guarantees by design:
* immutability of any file in the filesystem
* ensures it can verify the integrity of any file within the filesystem (through cryptographic means)
* ability to scale to very large numbers of files without loss of performance (tree of directories based on hash of file content)
* efficient distribution of files at lated stage thanks to the slicing in small chunks
'''
class MultihashFS(HashFS):
	def __init__(self, path, blocksize = 256*1024, levels=2):
		super(MultihashFS, self).__init__(path, blocksize, levels)
		self._levels = levels
		if levels < 1: self._levels = 1
		if levels > 22: self.levels = 22

	def _get_hashpath(self, filename):
		h = self._get_hash(filename, start=5)
		return os.path.join(self._path  , h, filename)

	def _store_chunk(self, filename, data):
		fullpath = self._get_hashpath(filename)
		ensure_path_exists(os.path.dirname(fullpath))

		if os.path.isfile(fullpath) == True:
			log.debug("HashFS: chunk [%s]-[%d] already exists" % (filename, len(data)))
			return False

		if data != None:
			log.info("HashFS: add chunk [%s]-[%d]" % (filename, len(data)))
			with open(fullpath, 'wb') as f:
				f.write(data)
			return True

	def _check_integrity(self, cid, data):
		cid0 = self._digest(data)
		if cid == cid0:
			log.debug("HashFS: checksum verified for chunk [%s]" % (cid))
			return True
		log.error("HashFS: corruption detected for chunk [%s] - got [%s]" % (cid, cid0))
		return False

	def _digest(self, data):
		m = hashlib.sha256()
		m.update(data)
		h = m.hexdigest()
		mh = multihash.encode(bytes.fromhex(h), 'sha2-256')
		cid = CIDv1("dag-pb", mh)
		return str(cid)

	def put(self, srcfile):
		links = []
		with open(srcfile, 'rb') as f:
			while True:
				d = f.read(self._blk_size)
				if d:
					scid = self._digest(d)
					self._store_chunk(scid, d)
					links.append( {"Hash" : scid, "Size": len(d)} )
				else:
					break

		ls = json.dumps({ "Links" : links })
		scid = self._digest(ls.encode())
		self._store_chunk(scid, ls.encode())

		self._log(scid, links)
		return scid


	def get(self, objectkey, dstfile):
		size = 0

		# Get all file chunks definition
		jl = json_load(self._get_hashpath(objectkey))
		if self._check_integrity(objectkey, json.dumps(jl).encode()) == False:
			return size

		corruption_found = False
		# concat all chunks to dstfile
		with open(dstfile, 'wb') as f:
			for chunk in jl["Links"]:
				h = chunk["Hash"]
				s = chunk["Size"]
				log.debug("HashFS: get chunk [%s]-[%d]" % (h, s))
				size += int(s)
				with open(self._get_hashpath(h), 'rb') as c:
					while True:
						d = c.read(self._blk_size)
						if not d: break
						if self._check_integrity(h, d) == False:
							corruption_found = True
							break
						f.write(d)
				if corruption_found == True: break

		if corruption_found == True:
			size = 0
			os.unlink(dstfile)
		return size

	def exists(self, key):
		return False

	'''Checks integrity of all files under .mlgit/<repotype>/objects'''
	def fsck(self, exclude=["files", "metadata"]):
		exclude.append(self._log)

		corruption_found = False
		log.info("HashFS: starting integrity check on [%s]" % (self._path))
		for root, dirs, files in os.walk(self._path):
			for exc in exclude:
				if exc in root: continue

			for file in files:
				fullpath = os.path.join(root, file)
				with open(fullpath, 'rb') as c:
					while True:
						d = c.read(self._blk_size)
						if not d: break
						if check_integrity(file, d) == False:
							corruption_found = True
		return corruption_found

if __name__=="__main__":
	try:
		os.mkdir("/tmp/hashfs-test")
	except:
		pass
	hfs = MultihashFS("/tmp/hashfs-test/")
	scid = hfs.put("test/data/think-hires.jpg")
	for files in hfs.walk():
		print(files)


