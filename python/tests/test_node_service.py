import unittest
import collections
import weakref
import numpy
import json

from libdvid import DVIDNodeService, ConnectionMethod, Slice2D, BlockZYX, SubstackZYX, PointZYX, ErrMsg
from _test_utils import TEST_DVID_SERVER, get_testrepo_root_uuid, delete_all_data_instances


class Test_DVIDNodeService(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.uuid = get_testrepo_root_uuid()
    
    @classmethod
    def tearDownClass(cls):
        delete_all_data_instances(cls.uuid)

    def test_default_user(self):
        # For backwards compatibility, make sure we can create a
        # DVIDNodeService without supplying a user name
        node_service = DVIDNodeService(TEST_DVID_SERVER, self.uuid)

    def test_custom_request(self):
        node_service = DVIDNodeService(TEST_DVID_SERVER, self.uuid, "foo@bar.com", "test_custom_app")
        response_body = node_service.custom_request( "log", "", ConnectionMethod.GET )
         
        # This shouldn't raise an exception
        json_data = json.loads(response_body)
 
    def test_keyvalue(self):
        node_service = DVIDNodeService(TEST_DVID_SERVER, self.uuid, "foo@bar.com", "test_keyvalue_app")
        node_service.create_keyvalue("keyvalue_test")
        node_service.put("keyvalue_test", "key1", "val1")
        readback_value = node_service.get("keyvalue_test", "key1")
        self.assertEqual(readback_value, "val1")

        node_service.put("keyvalue_test", "key2", "val2")
        readback_value = node_service.get("keyvalue_test", "key2")
        self.assertEqual(readback_value, "val2")

        keys = node_service.get_keys("keyvalue_test")
        assert isinstance(keys, collections.Iterable)
        assert set(keys) == set(["key1", "key2"])
  
        with self.assertRaises(ErrMsg):
            node_service.put("keyvalue_test", "key1", 123) # 123 is not a buffer.
 
    def test_grayscale_3d(self):
        node_service = DVIDNodeService(TEST_DVID_SERVER, self.uuid, "foo@bar.com", "test_gray_app")
        node_service.create_grayscale8("test_grayscale_3d")
        data = numpy.random.randint(0, 255, (128,128,128)).astype(numpy.uint8)
        assert data.flags['C_CONTIGUOUS']
        node_service.put_gray3D( "test_grayscale_3d", data, (0,0,0) )
        retrieved_data = node_service.get_gray3D( "test_grayscale_3d", (30,31,32), (20,20,20) )
        self.assertTrue( (retrieved_data == data[20:50, 20:51, 20:52]).all() )
 
    def test_for_memory_leak(self):
        """
        When DVIDNodeService uses array data from python or gives it to python,
        it shouldn't hold on to references to that data once Python is finished with it.

        Here, we use python's weakref module to see if any objects returned from
        DVIDNodeService (or given to it) linger longer than they are supposed to.
        """
        def get_bases(a):
            """
            Return a list of all 'bases' (parents) of
            the given array, including the array itself.
            """
            if a is None:
                return []
            if not isinstance(a.base, numpy.ndarray):
                return [a.base]
            return [a] + get_bases(a.base)

        node_service = DVIDNodeService(TEST_DVID_SERVER, self.uuid, "foo@bar.com", "test_mem_app")
        node_service.create_grayscale8("test_memoryleak_grayscale_3d")
        
        data = numpy.random.randint(0, 255, (128,128,128)).astype(numpy.uint8)
        assert data.flags['C_CONTIGUOUS']
        
        w = weakref.ref(data)
        node_service.put_gray3D( "test_memoryleak_grayscale_3d", data, (0,0,0) )
        del data
        assert w() is None, "put_gray3D() kept a reference to the data we gave it!"

        retrieved_data = node_service.get_gray3D( "test_memoryleak_grayscale_3d", (128,128,128), (0,0,0) )

        weak_bases = map(weakref.ref, get_bases(retrieved_data))
        del retrieved_data
        assert all([w() is None for w in weak_bases]), \
            "Data retuned by get_gray3D() wasn't released after we deleted our reference to it!"
 
    def test_labels_3d(self):
        node_service = DVIDNodeService(TEST_DVID_SERVER, self.uuid, "foo@bar.com", "test_label_app")
        node_service.create_labelblk("test_labels_3d")
        lblksize = node_service.get_blocksize("test_labels_3d")

        self.assertEqual(32, lblksize)
        
        
        node_service.create_labelblk("test_labels_3d64", "", 64)
        lblksize64 = node_service.get_blocksize("test_labels_3d64")
        self.assertEqual(64, lblksize64)
       
        data = numpy.random.randint(0, 2**63-1, (128,128,128)).astype(numpy.uint64)
        assert data.flags['C_CONTIGUOUS']
        node_service.put_labels3D( "test_labels_3d", data, (0,0,0) )
        retrieved_data = node_service.get_labels3D( "test_labels_3d", (30,31,32), (20,20,20) )
        self.assertTrue( (retrieved_data == data[20:50, 20:51, 20:52]).all() )
 
    def test_labels_3d_volsync(self):
        node_service = DVIDNodeService(TEST_DVID_SERVER, self.uuid, "foo@bar.com", "test_labelvol_app")
        node_service.create_labelblk("test_labels_3d2", "test_labels_3d2_vol")
        data = numpy.random.randint(0, 2**63-1, (128,128,128)).astype(numpy.uint64)
        assert data.flags['C_CONTIGUOUS']
        node_service.put_labels3D( "test_labels_3d2", data, (0,0,0) )
        retrieved_data = node_service.get_labels3D( "test_labels_3d2", (30,31,32), (20,20,20) )
        self.assertTrue( (retrieved_data == data[20:50, 20:51, 20:52]).all() )
  
    def test_labelarray_put_single_block(self):
        node_service = DVIDNodeService(TEST_DVID_SERVER, self.uuid, "foo@bar.com", "test_labelarray_put_single_block")
        node_service.create_labelarray("test_labelarray64", 64)
        data = numpy.random.randint(0, 10, (64,64,64)).astype(numpy.uint64)
        node_service.put_labelblocks3D( "test_labelarray64", data, (0,0,64) )
        retrieved_data = node_service.get_labels3D( "test_labelarray64", (64,64,64), (0,0,64) )
        assert (retrieved_data == data[:64,:64,:64]).all()
    
    def test_labelarray_put_volumes(self):
        node_service = DVIDNodeService(TEST_DVID_SERVER, self.uuid, "foo@bar.com", "test_labelarray_put_single_block")
        node_service.create_labelarray("test_labelarray64", 64)
        data = numpy.random.randint(0, 10, (128,128,128)).astype(numpy.uint64)
        assert data.flags['C_CONTIGUOUS']

        node_service.put_labelblocks3D( "test_labelarray64", data, (0,0,0) )
        retrieved_data = node_service.get_labels3D( "test_labelarray64", (30,31,32), (20,20,20) )
        assert (retrieved_data == data[20:50, 20:51, 20:52]).all()
    
        retrieved_data = node_service.get_labels3D( "test_labelarray64", (64,64,64), (0,0,0) )
        assert (retrieved_data == data[:64,:64,:64]).all()
    
        retrieved_data = node_service.get_labels3D( "test_labelarray64", (128,128,128), (0,0,0) )
        assert (retrieved_data == data).all()
        
    @unittest.skip("FIXME: No way to create tile data via the DVID http API.")
    def test_grayscale_2d_tile(self):
        # Create tile data here...
 
        # Now retrieve a tile.
        retrieved_tile = node_service.get_tile_slice( "test_grayscale_2d_tile", Slice2D.XY, 0, (0,0,0) )
     
    def test_roi(self):
        node_service = DVIDNodeService(TEST_DVID_SERVER, self.uuid, "foo@bar.com", "test_roi_app")
        node_service.create_roi("test_roi")
        node_service.post_roi("test_roi", [(1,2,3),(2,3,4),(4,5,6)])
        roi_blocks = node_service.get_roi("test_roi")
        self.assertEqual(roi_blocks, [(1,2,3),(2,3,4),(4,5,6)])

    def test_roi_2(self):
        # Create X-shaped ROI
        # This ensures that the x-run encoding within our ROI message works properly
        # (There used to be a bug in post_roi() that would have broken this test.)

        _ = 0
        # 8x8 blocks = 256x256 px
        roi_mask_yx = numpy.array( [[1,_,_,_,_,_,_,1],
                                    [1,1,_,_,_,_,1,1],
                                    [_,1,1,_,_,1,1,_],
                                    [_,_,1,1,1,1,_,_],
                                    [_,_,_,1,1,_,_,_],
                                    [_,_,1,1,1,1,_,_],
                                    [_,1,1,_,_,1,1,_],
                                    [1,1,_,_,_,_,1,1] ])
    
        roi_mask_zyx = numpy.zeros( (8,8,8) )
        roi_mask_zyx[:] = roi_mask_yx[None, :, :]
        roi_block_indexes = numpy.transpose( roi_mask_zyx.nonzero() )
    
        ns = DVIDNodeService(TEST_DVID_SERVER, self.uuid, "foo@bar.com", "test_roi_2_app")
        ns.create_roi('test-diagonal-256')
        ns.post_roi('test-diagonal-256', roi_block_indexes)

        fetched_blocks = ns.get_roi("test-diagonal-256")
        fetched_blocks = numpy.array(fetched_blocks)

        # Both arrays happen to be sorted already
        assert ( fetched_blocks == roi_block_indexes ).all()

    def test_roi_3d(self):
        node_service = DVIDNodeService(TEST_DVID_SERVER, self.uuid, "foo@bar.com", "test_roi3d_app")
        node_service.create_roi("test_roi_3d")
        
        # Create an upside-down L-shaped roi in the first 4 blocks:
        # 
        # 1 1
        # 1 0
        node_service.post_roi("test_roi_3d", [(0,0,0),(1,0,0),(0,1,0)])

        expected_data = numpy.ones((64,64,32), dtype=numpy.uint8, order='C')
        expected_data[32:, 32:] = 0

        retrieved_data = node_service.get_roi3D( "test_roi_3d", (64,64,32), (0,0,0) )
        self.assertEqual( retrieved_data.shape, expected_data.shape )
        self.assertTrue( (retrieved_data == expected_data).all() )

    def test_roi_partition(self):
        node_service = DVIDNodeService(TEST_DVID_SERVER, self.uuid, "foo@bar.com", "test_part_app")
        node_service.create_roi("test_roi_partition")
         
        blocks = [(0,0,0),(1,1,1),(2,2,2),(3,3,3)]
        node_service.post_roi("test_roi_partition", blocks)
        substacks, packing_factor = node_service.get_roi_partition("test_roi_partition", 4)
         
        self.assertEqual(substacks, [SubstackZYX(4*32,0,0,0)])
        self.assertEqual( packing_factor, float(len(blocks))/(len(substacks) * 4**3) )
 
        blocks += [(4,0,0)]
        node_service.post_roi("test_roi_partition", blocks)
        substacks, packing_factor = node_service.get_roi_partition("test_roi_partition", 4)
  
        self.assertEqual(substacks, [SubstackZYX(4*32,0,0,0), SubstackZYX(4*32,128,0,0)])
  
        # FIXME: DVID returns "NumActiveBlocks: 8" here, even though there should only be 5.
        #        That's wack, right?
        #  self.assertEqual( packing_factor, float(len(blocks))/(len(substacks) * 4**3) )
 
    def test_roi_ptquery(self):
        node_service = DVIDNodeService(TEST_DVID_SERVER, self.uuid, "foo@bar.com", "test_ptquery2 app")
        node_service.create_roi("test_roi")
        node_service.post_roi("test_roi", [(1,2,3),(2,3,4),(4,5,6)])
        query_results = node_service.roi_ptquery( "test_roi", [(0,0,0), (32, 64, 32*3)] )
        self.assertEqual( query_results, [False, True] )        

if __name__ == "__main__":
    unittest.main()
