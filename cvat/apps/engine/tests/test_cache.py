# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

import io
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from cvat.apps.engine.cache import Callback, MediaCache


def _make_cache_item(data: bytes, timestamp: datetime):
    return (io.BytesIO(data), "image/jpeg", MediaCache._get_checksum(data), timestamp)


class TestMediaCache(unittest.TestCase):
    def test_stale_timestamp_cache_item_is_recreated_once(self):
        cache = MediaCache()
        key = "segment_1_chunk_0_100"
        expected_ts = datetime(2026, 6, 11, tzinfo=timezone.utc)
        stale_item = _make_cache_item(b"stale", expected_ts - timedelta(seconds=1))
        fresh_item = _make_cache_item(b"fresh", expected_ts + timedelta(seconds=1))
        create_callback = Callback(lambda: (io.BytesIO(b"fresh"), "image/jpeg"))

        with (
            mock.patch.object(cache, "_get_or_set_cache_item", return_value=stale_item),
            mock.patch.object(cache, "_delete_cache_item") as delete_cache_item,
            mock.patch.object(
                cache, "_create_cache_item", return_value=fresh_item
            ) as create_cache_item,
        ):
            item = cache._get_or_set_cache_item_with_timestamp_validation(
                key,
                create_callback,
                lambda: expected_ts,
            )

        self.assertIs(item, fresh_item)
        delete_cache_item.assert_called_once_with(key)
        create_cache_item.assert_called_once_with(
            key,
            create_callback,
            cache_item_ttl=None,
        )

    def test_fresh_timestamp_cache_item_is_reused(self):
        cache = MediaCache()
        key = "segment_1_chunk_0_100"
        expected_ts = datetime(2026, 6, 11, tzinfo=timezone.utc)
        fresh_item = _make_cache_item(b"fresh", expected_ts)
        create_callback = Callback(lambda: (io.BytesIO(b"fresh"), "image/jpeg"))

        with (
            mock.patch.object(cache, "_get_or_set_cache_item", return_value=fresh_item),
            mock.patch.object(cache, "_delete_cache_item") as delete_cache_item,
            mock.patch.object(cache, "_create_cache_item") as create_cache_item,
        ):
            item = cache._get_or_set_cache_item_with_timestamp_validation(
                key,
                create_callback,
                lambda: expected_ts,
            )

        self.assertIs(item, fresh_item)
        delete_cache_item.assert_not_called()
        create_cache_item.assert_not_called()
