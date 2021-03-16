"""
© Copyright 2020 HP Development Company, L.P.
SPDX-License-Identifier: GPL-2.0-only
"""

import os
import shutil
import unittest
from copy import deepcopy
from unittest import mock

import pytest
from git import GitError, Repo
from prettytable import PrettyTable

from ml_git.constants import STORAGE_KEY
from ml_git.metadata import Metadata
from ml_git.repository import Repository
from ml_git.utils import clear, yaml_load_str, yaml_load
from ml_git.utils import yaml_save, ensure_path_exists
from tests.unit.conftest import MODELS, DATASETS, LABELS, S3

files_mock = {'zdj7Wm99FQsJ7a4udnx36ZQNTy7h4Pao3XmRSfjo4sAbt9g74': {'1.jpg'},
              'zdj7WnVtg7ZgwzNxwmmDatnEoM3vbuszr3xcVuBYrcFD6XzmW': {'2.jpg'},
              'zdj7Wi7qy2o3kgUC72q2aSqzXV8shrererADgd6NTP9NabpvB': {'3.jpg'},
              'zdj7We7FUbukkozcTtYgcsSnLWGqCm2PfkK53nwJWLHEtuef4': {'6.jpg'},
              'zdj7WZzR8Tw87Dx3dm76W5aehnT23GSbXbQ9qo73JgtwREGwB': {'7.jpg'},
              'zdj7WfQCZgACUxwmhVMBp4Z2x6zk7eCMUZfbRDrswQVUY1Fud': {'8.jpg'},
              'zdj7WdjnTVfz5AhTavcpsDT62WiQo4AeQy6s4UC1BSEZYx4NP': {'9.jpg'},
              'zdj7WXiB8QrNVQ2VABPvvfC3VW6wFRTWKvFhUW5QaDx6JMoma': {'10.jpg'}}

spec = 'dataset-ex'
spec_2 = 'dataset-ex-2'
index_path = './mdata'
config = {
    'mlgit_path': './mdata',
    'mlgit_conf': 'config.yaml',

    DATASETS: {
        'git': os.path.join(os.getcwd(), 'git_local_server.git'),
    },
    LABELS: {
        'git': os.path.join(os.getcwd(), 'git_local_server.git'),
    },
    MODELS: {
        'git': os.path.join(os.getcwd(), 'git_local_server.git'),
    },


    STORAGE_KEY: {
        S3: {
            'mlgit-datasets': {
                'region': 'us-east-1',
                'aws-credentials': {'profile': 'mlgit'}
            }
        }
    },

    'verbose': 'info',
}

metadata_config = {
    DATASETS: {
        'categories': 'images',
        'manifest': {
            'files': 'MANIFEST.yaml',
            STORAGE_KEY: 's3h://ml-git-datasets'
        },
        'name': 'dataset_ex',
        'version': 1
    }
}


@pytest.mark.usefixtures('test_dir')
class MetadataTestCases(unittest.TestCase):

    @pytest.mark.usefixtures('start_local_git_server', 'switch_to_test_dir')
    def test_init(self):
        m = Metadata(spec, self.test_dir, config, DATASETS)
        m.init()
        self.assertTrue(m.check_exists())
        clear(m.path)

    @pytest.mark.usefixtures('start_local_git_server', 'switch_to_test_dir')
    def test_metadata_tag(self):
        m = Metadata(spec, index_path, config, DATASETS)
        tag = m.metadata_tag(metadata_config)
        self.assertEqual(tag, 'images__dataset_ex__1')

    @pytest.mark.usefixtures('start_local_git_server', 'switch_to_test_dir')
    def test_tag_exist(self):
        mdpath = os.path.join(self.test_dir, 'metadata')
        ws_path = os.path.join(self.test_dir, DATASETS)
        specpath = 'dataset-ex'
        ensure_path_exists(os.path.join(mdpath, specpath))
        ensure_path_exists(os.path.join(ws_path, specpath))
        shutil.copy('hdata/dataset-ex.spec', os.path.join(mdpath, specpath) + '/dataset-ex.spec')
        shutil.copy('hdata/dataset-ex.spec', os.path.join(ws_path, specpath) + '/dataset-ex.spec')
        manifestpath = os.path.join(os.path.join(mdpath, specpath), 'MANIFEST.yaml')
        yaml_save(files_mock, manifestpath)

        config['mlgit_path'] = self.test_dir
        m = Metadata(specpath, mdpath, config, DATASETS)
        r = Repository(config, DATASETS)
        r.init()

        fullmetadatapath, categories_subpath, metadata = m.tag_exists(self.test_dir)
        self.assertFalse(metadata is None)

    @pytest.mark.usefixtures('start_local_git_server', 'switch_to_test_dir')
    def test_clone_config_repo(self):
        m = Metadata('', self.test_dir, config, DATASETS)
        m.clone_config_repo()
        self.assertTrue(m.check_exists())

    @pytest.mark.usefixtures('start_local_git_server', 'switch_to_test_dir')
    def test_get_tag(self):
        mdpath = os.path.join(self.test_dir, 'metadata')
        specpath = 'dataset-ex'
        ensure_path_exists(os.path.join(mdpath, specpath))
        shutil.copy('hdata/dataset-ex.spec', os.path.join(mdpath, specpath) + '/dataset-ex.spec')
        manifestpath = os.path.join(os.path.join(mdpath, specpath), 'MANIFEST.yaml')
        yaml_save(files_mock, manifestpath)

        config['mlgit_path'] = self.test_dir
        m = Metadata(specpath, mdpath, config, DATASETS)
        r = Repository(config, DATASETS)
        r.init()

        tag_list = ['computer__images__dataset-ex__1']
        with mock.patch('ml_git.metadata.Metadata.list_tags', return_value=tag_list):
            target_tag = m.get_tag(specpath, -1)
        self.assertEqual(target_tag, tag_list[0])
        clear(m.path)

    @pytest.mark.usefixtures('start_local_git_server', 'switch_to_test_dir')
    def test_get_target_tag(self):
        tags = ['computer__images__dataset-ex__1',
                'computer__images__dataset-ex__2',
                'computer__videos__dataset-ex__1']
        m = Metadata('', self.test_dir, config, DATASETS)
        self.assertRaises(RuntimeError, lambda: m._get_target_tag(tags, 'dataset-ex', -1))
        self.assertRaises(RuntimeError, lambda: m._get_target_tag(tags, 'dataset-ex', 1))
        self.assertRaises(RuntimeError, lambda: m._get_target_tag(tags, 'dataset-wrong', 1))
        self.assertEqual(m._get_target_tag(tags, 'dataset-ex', 2), 'computer__images__dataset-ex__2')
        clear(m.path)

    @pytest.mark.usefixtures('start_local_git_server', 'switch_to_test_dir')
    def test_clone_empty_config_repo(self):
        config = {
            'mlgit_path': './mdata',
            'mlgit_conf': 'config.yaml',
            'verbose': 'info',
            DATASETS: {'git': '', },
            LABELS: {'git': '', },
            MODELS: {'git': '', }, }

        m = Metadata('', self.test_dir, config, DATASETS)
        m.clone_config_repo()
        self.assertFalse(m.check_exists())

    @pytest.mark.usefixtures('start_local_git_server', 'switch_to_test_dir')
    def test_blank_remote_url(self):
        config_cp = deepcopy(config)
        config_cp[DATASETS]['git'] = ''
        m = Metadata(spec, self.test_dir, config_cp, DATASETS)
        self.assertRaises(GitError, m.validate_blank_remote_url)
        clear(m.path)

    @pytest.mark.usefixtures('start_local_git_server', 'switch_to_test_dir')
    def test_delete_git_reference(self):
        m = Metadata(spec, self.test_dir, config, DATASETS)
        m.init()

        for url in Repo(m.path).remote().urls:
            self.assertNotEqual(url, '')

        self.assertTrue(m.delete_git_reference())

        for url in Repo(m.path).remote().urls:
            self.assertEqual(url, '')

    @pytest.mark.usefixtures('start_local_git_server', 'switch_to_test_dir', 'change_branch_name')
    def test_default_branch(self):
        default_branch_for_empty_repo = 'master'
        new_branch = 'main'
        m = Metadata('', self.test_dir, config, DATASETS)
        m.init()
        self.assertTrue(m.check_exists())
        self.assertEqual(m.get_default_branch(), default_branch_for_empty_repo)
        self.change_branch(m.path, new_branch)
        self.assertNotEqual(m.get_default_branch(), default_branch_for_empty_repo)
        self.assertEqual(m.get_default_branch(), new_branch)
        clear(m.path)

    @pytest.mark.usefixtures('start_local_git_server', 'switch_to_test_dir')
    def test_get_spec_content_from_ref(self):
        mdpath = os.path.join(self.test_dir, 'mdata', DATASETS, 'metadata')
        specpath = 'dataset-ex'
        m = Metadata(specpath, self.test_dir, config, DATASETS)
        m.init()
        ensure_path_exists(os.path.join(mdpath, specpath))
        spec_metadata_path = os.path.join(mdpath, specpath) + '/dataset-ex.spec'
        shutil.copy('hdata/dataset-ex.spec', spec_metadata_path)

        sha = m.commit(spec_metadata_path, specpath)
        tag = m.tag_add(sha)
        path = 'dataset-ex/dataset-ex.spec'
        content = yaml_load_str(m._get_spec_content_from_ref(tag.commit, path))
        spec_file = yaml_load(spec_metadata_path)
        self.assertEqual(content, spec_file)

    @pytest.mark.usefixtures('start_local_git_server', 'switch_to_test_dir')
    def test_get_specs_to_compare(self):
        mdpath = os.path.join(self.test_dir, 'mdata', DATASETS, 'metadata')
        specpath = 'dataset-ex'
        m = Metadata(specpath, self.test_dir, config, DATASETS)
        m.init()
        ensure_path_exists(os.path.join(mdpath, specpath))
        spec_metadata_path = os.path.join(mdpath, specpath) + '/dataset-ex.spec'
        shutil.copy('hdata/dataset-ex.spec', spec_metadata_path)

        sha = m.commit(spec_metadata_path, specpath)
        m.tag_add(sha)
        specs = m.get_specs_to_compare(specpath, DATASETS)
        spec_file = yaml_load(spec_metadata_path)
        for c, v in specs:
            self.assertEqual(c, spec_file[DATASETS]['manifest'])
            self.assertIsNotNone(v, {DATASETS: {'manifest': {}}})

    @pytest.mark.usefixtures('start_local_git_server', 'switch_to_test_dir')
    def test_get_metrics(self):
        repo_type = MODELS
        mdpath = os.path.join(self.test_dir, 'mdata', repo_type, 'metadata')
        specpath = os.path.join('vision-computer', 'images')
        entity = 'model-ex'
        m = Metadata(entity, self.test_dir, config, repo_type)
        m.init()
        ensure_path_exists(os.path.join(mdpath, specpath, entity))
        spec_metadata_path = os.path.join(mdpath, specpath, entity, 'model-ex.spec')
        shutil.copy('hdata/dataset-ex.spec', spec_metadata_path)

        spec_file = yaml_load(spec_metadata_path)
        spec_file[repo_type] = deepcopy(spec_file[DATASETS])
        del spec_file[DATASETS]
        spec_file[repo_type]['metrics'] = {'metric_1': 0, 'metric_2': 1}
        yaml_save(spec_file, spec_metadata_path)

        tag = 'vision-computer__images__model-ex__1'
        sha = m.commit(spec_metadata_path, specpath)
        m.tag_add(tag)

        metrics = m._get_metrics(entity, tag, sha)

        test_table = PrettyTable()
        test_table.field_names = ['Name', 'Value']
        test_table.align['Name'] = 'l'
        test_table.align['Value'] = 'l'
        test_table.add_row(['metric_1', 0])
        test_table.add_row(['metric_2', 1])
        test_metrics = '\nmetrics:\n{}'.format(test_table.get_string())

        self.assertEqual(metrics, test_metrics)

    @pytest.mark.usefixtures('start_local_git_server', 'switch_to_test_dir')
    def test_get_metrics_without_metrics(self):
        repo_type = MODELS
        mdpath = os.path.join(self.test_dir, 'mdata', repo_type, 'metadata')
        specpath = os.path.join('vision-computer', 'images')
        entity = 'model-ex'
        m = Metadata(entity, self.test_dir, config, repo_type)
        m.init()
        ensure_path_exists(os.path.join(mdpath, specpath, entity))
        spec_metadata_path = os.path.join(mdpath, specpath, entity) + '/model-ex.spec'
        shutil.copy('hdata/dataset-ex.spec', spec_metadata_path)

        spec_file = yaml_load(spec_metadata_path)
        spec_file[repo_type] = deepcopy(spec_file[DATASETS])
        del spec_file[DATASETS]
        yaml_save(spec_file,  spec_metadata_path)

        tag = 'vision-computer__images__model-ex__1'
        sha = m.commit(spec_metadata_path, specpath)
        m.tag_add(tag)

        metrics = m._get_metrics(entity, tag, sha)

        self.assertEqual(metrics, '')
