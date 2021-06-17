"""
© Copyright 2021 HP Development Company, L.P.
SPDX-License-Identifier: GPL-2.0-only
"""

import io
import os
import tempfile
import urllib

from ml_git.constants import FileType
from ml_git.utils import create_csv_file


def is_minio_storage(storage):
    """Returns True if the endpoint-url field is present and is not null."""
    return 'endpoint-url' in storage and storage['endpoint-url']


def format_storages(storages):
    """Augment existing storage information with server type, etc."""
    try:
        for bucket_type, buckets in storages.items():
            for bucket_name, bucket in buckets.items():
                bucket['name'] = bucket_name
                bucket['type'] = bucket_type
                bucket['subtype'] = ''
                if bucket_type in ('s3', 's3h'):
                    bucket['subtype'] = 'minio' if is_minio_storage(bucket) else 'aws'
    except Exception:
        print('Error augmenting storage information')
    return storages


def get_repo_name_from_url(repository_url: str) -> str:
    """Returns the Github repository full name from a git url or usual url format string."""
    if '://' in repository_url:
        return urllib.parse.urlparse(repository_url).path[1:].replace('.git', '')
    return repository_url.replace('.git', '').split(':')[-1]


def __format_relationships_to_csv_data(entity_name, entity_type, relationships, formatted_data=None):
    for value in relationships[entity_name]:
        from_entity_version = value.version
        from_entity_tag = value.tag
        for to_entity in value.relationships:
            formatted_data.append({
                'from_tag': from_entity_tag,
                'from_name': entity_name,
                'from_version': from_entity_version,
                'from_type': entity_type,
                'to_tag': to_entity.tag,
                'to_name': to_entity.name,
                'to_version': to_entity.version,
                'to_type': to_entity.entity_type
            })
    return formatted_data


def export_relationships_to_csv(entities, relationships, export_path):
    csv_header = ['from_tag', 'from_name', 'from_version', 'from_type', 'to_tag', 'to_name', 'to_version', 'to_type']
    formatted_data = []
    for entity in entities:
        formatted_data = __format_relationships_to_csv_data(entity.name, entity.entity_type, relationships, formatted_data)

    file_name_prefix = 'project'
    if len(entities) == 1:
        file_name_prefix = entities[0].name
    file_name = '{}_relationships.{}'.format(file_name_prefix, FileType.CSV.value)

    if export_path is None:
        with tempfile.TemporaryDirectory() as tempdir:
            file_path = os.path.join(tempdir, file_name)
            create_csv_file(file_path, csv_header, formatted_data)
            with open(file_path) as csv_file:
                return io.StringIO(csv_file.read())
    else:
        file_path = os.path.join(export_path, file_name)
        create_csv_file(file_path, csv_header, formatted_data)
        print('A CSV file was created with the relationship information in {}'.format(file_path))
        with open(file_path) as csv_file:
            return io.StringIO(csv_file.read())
