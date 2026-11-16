using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using OtxCSLib.Utilities;

namespace OtxDataBaseLayer.Database.BtrieveAPI;

public static class BtrieveInterface
{
	private static object OperationLock = new object();

	public const int Bnolock = 0;

	public const int Bsilock = 200;

	public const int Bmulock = 400;

	public const int Bopnow = 200;

	public const int Bsiwaitlock = 100;

	public const int Bmuwaitlock = 300;

	public const int BnoWaitOnWrite = 500;

	public const int Bconctrans = 1000;

	public const int Bdupl = 1;

	public const int Bmod = 2;

	public const int Bbin = 4;

	public const int Bnull = 8;

	public const int Bseg = 16;

	public const int Balt = 32;

	public const int Bdes = 64;

	public const int Bext = 256;

	public const int Bnany = 512;

	public const int Bncase = 1024;

	public const int Bstring = 0;

	public const int Binteger = 1;

	public const int Bfloat = 2;

	public const int Bdate = 3;

	public const int Btime = 4;

	public const int Bdecimal = 5;

	public const int Bmoney = 6;

	public const int Blogical = 7;

	public const int Bnumeric = 8;

	public const int Bbfloat = 9;

	public const int Blstring = 10;

	public const int Bzstring = 11;

	public const int Bubinary = 14;

	public const int Bautoinc = 15;

	public const int VAR_RECS = 1;

	public const int BLANK_TRUNC = 2;

	public const int PRE_ALLOC = 4;

	public const int DATA_COMP = 8;

	public const int KEY_ONLY = 16;

	public const int BALANCED_KEYS = 32;

	public const int FREE_10 = 64;

	public const int FREE_20 = 128;

	public const int FREE_30 = 192;

	public const int DUP_PTRS = 256;

	public const int INCLUDE_SYSTEM_DATA = 512;

	public const int SPECIFY_KEY_NUMS = 1024;

	public const int VATS_SUPPORT = 2048;

	public const int NO_INCLUDE_SYSTEM_DATA = 4608;

	private const int POS_BLOCK_SIZE = 128;

	[DllImport("BTRIEVEINTERFACE", EntryPoint = "BTRCALL")]
	private static extern short BtrCall(ushort operation, IntPtr posBlock, IntPtr dataBuffer, ref int dataLength, IntPtr keyBuffer, byte keyLength, byte ckeynum);

	[DllImport("BTRIEVEINTERFACE64", EntryPoint = "BTRCALL")]
	private static extern short BtrCall64(ushort operation, IntPtr posBlock, IntPtr dataBuffer, ref int dataLength, IntPtr keyBuffer, byte keyLength, byte ckeynum);

	public static void Test()
	{
	}

	public static Error BtrieveOperation(OperationCode opCode, byte[] positionBlock, byte[] data, ref int dataLength, byte[] key, byte keyLength, byte keyNum)
	{
		lock (OperationLock)
		{
			IntPtr intPtr = IntPtr.Zero;
			IntPtr intPtr2 = IntPtr.Zero;
			IntPtr intPtr3 = IntPtr.Zero;
			if (data != null)
			{
				intPtr = Marshal.AllocHGlobal(data.Length);
				Marshal.Copy(data, 0, intPtr, data.Length);
			}
			if (positionBlock != null)
			{
				intPtr2 = Marshal.AllocHGlobal(128);
				Marshal.Copy(positionBlock, 0, intPtr2, positionBlock.Length);
			}
			if (key != null)
			{
				intPtr3 = Marshal.AllocHGlobal(keyLength);
				Marshal.Copy(key, 0, intPtr3, key.Length);
			}
			short result = 0;
			try
			{
				result = ((!Environment.Is64BitProcess) ? BtrCall((ushort)opCode, intPtr2, intPtr, ref dataLength, intPtr3, keyLength, keyNum) : BtrCall64((ushort)opCode, intPtr2, intPtr, ref dataLength, intPtr3, keyLength, keyNum));
				if (intPtr != IntPtr.Zero)
				{
					Marshal.Copy(intPtr, data, 0, dataLength);
				}
				if (intPtr2 != IntPtr.Zero)
				{
					Marshal.Copy(intPtr2, positionBlock, 0, 128);
				}
				if (intPtr3 != IntPtr.Zero)
				{
					Marshal.Copy(intPtr3, key, 0, keyLength);
				}
			}
			catch
			{
				throw;
			}
			finally
			{
				if (intPtr != IntPtr.Zero)
				{
					Marshal.FreeHGlobal(intPtr);
				}
				if (intPtr2 != IntPtr.Zero)
				{
					Marshal.FreeHGlobal(intPtr2);
				}
				if (intPtr3 != IntPtr.Zero)
				{
					Marshal.FreeHGlobal(intPtr3);
				}
			}
			return (Error)result;
		}
	}

	public static Error OpenFile(string path, OpenMode openMode, ref byte[] position)
	{
		if (path.Length > 255)
		{
			throw new Exception("Path to long");
		}
		byte[] bytes = Encoding.Default.GetBytes(path);
		int num = 0;
		byte[] array = new byte[bytes.Length + 1];
		Array.Copy(bytes, array, bytes.Length);
		array[bytes.Length] = 0;
		position = new byte[128];
		byte[] array2 = new byte[1];
		num = array2.Length;
		return BtrieveOperation(OperationCode.B_OPEN, position, array2, ref num, array, (byte)array.Length, (byte)openMode);
	}

	public static Error CloseFile(byte[] position)
	{
		_ = new byte[1];
		int num = new byte[1].Length;
		num = 0;
		return BtrieveOperation(OperationCode.B_CLOSE, position, null, ref num, null, 0, 0);
	}

	public static Error CreateFile(string path, t_btrieve_file_spec_STATIC fileSpec, List<t_btrieve_key_spec> listKeys)
	{
		List<byte[]> list = new List<byte[]>();
		list.Add(SerializationUtils.RawSerialize(fileSpec));
		foreach (t_btrieve_key_spec listKey in listKeys)
		{
			list.Add(SerializationUtils.RawSerialize(listKey));
		}
		byte[] array = SerializationUtils.ConvertToByteArray(list);
		int dataLength = array.Length;
		byte[] array2 = SerializationUtils.StringToArray(path, path.Length + 1);
		return BtrieveOperation(OperationCode.B_CREATE, null, array, ref dataLength, array2, (byte)array2.Length, 0);
	}

	public static Error GetRecord(byte[] position, OperationCode operationCode, byte[] data, ref int dataLength, int keyId, byte[] key)
	{
		if (position == null)
		{
			position = new byte[128];
		}
		dataLength = data.Length;
		return BtrieveOperation(operationCode, position, data, ref dataLength, key, (byte)key.Length, (byte)keyId);
	}

	public static Error GetFileStat(byte[] position, ref BtrieveFileStat fileStat)
	{
		int dataLength = 1000;
		byte keyLength = 0;
		byte[] array = new byte[dataLength];
		Error error = BtrieveOperation(OperationCode.B_STAT, position, array, ref dataLength, null, keyLength, byte.MaxValue);
		if (error == Error.B_NO_ERROR)
		{
			fileStat.Info = SerializationUtils.RawDeSerialize<t_btrieve_file_stat_v2>(array);
			int num = Marshal.SizeOf(typeof(t_btrieve_file_stat_v2));
			t_btrieve_key_stat item;
			do
			{
				item = SerializationUtils.RawDeSerialize<t_btrieve_key_stat>(array.Skip(num).ToArray());
				fileStat.KeySegments.Add(item);
				num += Marshal.SizeOf(typeof(t_btrieve_key_stat));
			}
			while (item.key_len != 0);
		}
		return error;
	}
}
