using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.InteropServices;
using OtxCSLib.Utilities;

namespace OtxDataBaseLayer.Database.BtrieveAPI;

public class BtrieveFile<KEY_TYPE> : BtrieveFileBase
{
	private byte[] Position;

	private int? ConstantRecordSize;

	private int KeyId;

	public KEY_TYPE LastKey;

	internal string FilePath;

	private List<object> ReadNextExtBuffer;

	public BtrieveFile(int keyId, bool readOnly = true, int? constantRecordSize = null)
	{
		KeyId = keyId;
		ReadOnly = readOnly;
		ConstantRecordSize = constantRecordSize;
	}

	public BtrieveFile(int keyId, string path, bool readOnly = true, int? constantRecordSize = null)
	{
		KeyId = keyId;
		ReadOnly = readOnly;
		ConstantRecordSize = constantRecordSize;
		FilePath = path;
	}

	public override void Open(string path = null)
	{
		if (path != null)
		{
			FilePath = path;
		}
		if (FilePath == null)
		{
			throw new Exception("No path specified");
		}
		if (Position != null)
		{
			throw new Exception("File already opend");
		}
		Error error = BtrieveInterface.OpenFile(FilePath, ReadOnly ? OpenMode.ReadOnly : OpenMode.Normal, ref Position);
		if (error != Error.B_NO_ERROR)
		{
			Position = null;
			throw new ExceptionBtrieve(error, path, OperationCode.B_OPEN);
		}
	}

	public override void Close()
	{
		ReadNextExtBuffer = null;
		Error error = BtrieveInterface.CloseFile(Position);
		if (error != Error.B_NO_ERROR)
		{
			throw new ExceptionBtrieve(error, FilePath, OperationCode.B_CLOSE);
		}
		Position = null;
	}

	public override RECORD_TYPE Read<RECORD_TYPE>(OperationCode operationCode, object key)
	{
		return Read<RECORD_TYPE>(operationCode, (KEY_TYPE)key);
	}

	public RECORD_TYPE Read<RECORD_TYPE>(OperationCode operationCode, KEY_TYPE key)
	{
		ReadNextExtBuffer = null;
		int dataLength = ((!ConstantRecordSize.HasValue) ? Marshal.SizeOf(typeof(RECORD_TYPE)) : ConstantRecordSize.Value);
		byte[] data = new byte[dataLength];
		byte[] array = SerializationUtils.RawSerialize(key);
		Error record = BtrieveInterface.GetRecord(Position, operationCode, data, ref dataLength, KeyId, array);
		if (record != Error.B_NO_ERROR)
		{
			throw new ExceptionBtrieve(record, FilePath, operationCode);
		}
		LastKey = SerializationUtils.RawDeSerialize<KEY_TYPE>(array);
		return SerializationUtils.RawDeSerialize<RECORD_TYPE>(data);
	}

	public RECORD_TYPE ReadNext<RECORD_TYPE>()
	{
		ReadNextExtBuffer = null;
		if (LastKey == null)
		{
			throw new Exception("Read operation not initialized");
		}
		return Read<RECORD_TYPE>(OperationCode.B_GET_NEXT, LastKey);
	}

	public RECORD_TYPE ReadNextExt<RECORD_TYPE>()
	{
		RECORD_TYPE val = default(RECORD_TYPE);
		if (LastKey == null)
		{
			throw new Exception("Read operation not initialized");
		}
		if (ReadNextExtBuffer == null)
		{
			ReadNextExtBuffer = new List<object>();
		}
		if (ReadNextExtBuffer.Count == 0)
		{
			FillReadNextExtBuffer<RECORD_TYPE>();
		}
		if (ReadNextExtBuffer.Count > 0)
		{
			val = (RECORD_TYPE)ReadNextExtBuffer.First();
			ReadNextExtBuffer.Remove(val);
			return val;
		}
		throw new ExceptionBtrieve(Error.B_END_OF_FILE, "", OperationCode.B_GET_NEXT_EXTENDED);
	}

	private void FillReadNextExtBuffer<RECORD_TYPE>()
	{
		Extended_Header_Type extended_Header_Type = new Extended_Header_Type();
		short num = (short)Marshal.SizeOf(typeof(RECORD_TYPE));
		int num2 = Marshal.SizeOf((object)extended_Header_Type);
		byte[] array = SerializationUtils.RawSerialize(LastKey);
		int dataLength = 64000;
		int num3 = (short)((dataLength - 2) / (num + 6));
		extended_Header_Type.nLength = (short)num2;
		extended_Header_Type.nFieldLen = num;
		extended_Header_Type.CtrlConst = new byte[2];
		extended_Header_Type.CtrlConst[0] = 69;
		extended_Header_Type.CtrlConst[1] = 71;
		extended_Header_Type.nRejectCount = 1;
		extended_Header_Type.nNoOfTerms = 0;
		extended_Header_Type.nNoOfFields = 1;
		extended_Header_Type.nFieldOfs = 0;
		extended_Header_Type.nNoOfRecToRet = (short)num3;
		byte[] array2 = new byte[dataLength];
		if (Position == null)
		{
			Position = new byte[128];
		}
		Array.Copy(SerializationUtils.RawSerialize(extended_Header_Type), array2, num2);
		Error error = BtrieveInterface.BtrieveOperation(OperationCode.B_GET_NEXT_EXTENDED, Position, array2, ref dataLength, array, (byte)array.Length, (byte)KeyId);
		if (error == Error.B_NO_ERROR || error == Error.B_END_OF_FILE)
		{
			byte[] array3 = new byte[2];
			Array.Copy(array2, array3, 2);
			int num4 = SerializationUtils.RawDeSerialize<ushort>(array3);
			for (int i = 0; i < num4; i++)
			{
				byte[] array4 = new byte[num];
				Array.Copy(array2, 2 + i * (num + 6) + 6, array4, 0, num);
				ReadNextExtBuffer.Add(SerializationUtils.RawDeSerialize<RECORD_TYPE>(array4));
			}
			LastKey = SerializationUtils.RawDeSerialize<KEY_TYPE>(array);
			return;
		}
		throw new ExceptionBtrieve(error, FilePath, OperationCode.B_GET_NEXT_EXTENDED);
	}

	public void InsertRecord(object record)
	{
		byte[] array = SerializationUtils.RawSerialize(record);
		if (ConstantRecordSize.HasValue)
		{
			if (array.Length > ConstantRecordSize.Value)
			{
				throw new ExceptionBtrieve(Error.B_DATALENGTH_ERROR, FilePath, OperationCode.B_INSERT);
			}
			if (array.Length < ConstantRecordSize.Value)
			{
				byte[] array2 = new byte[ConstantRecordSize.Value];
				Array.Copy(array, array2, array.Length);
				array = array2;
			}
		}
		int dataLength = array.Length;
		byte[] array3 = new byte[2];
		Error error = BtrieveInterface.BtrieveOperation(OperationCode.B_INSERT, Position, array, ref dataLength, array3, (byte)array3.Length, 0);
		if (error != Error.B_NO_ERROR)
		{
			throw new ExceptionBtrieve(error, FilePath, OperationCode.B_INSERT);
		}
	}

	public void UpdateRecord(object record)
	{
		byte[] array = SerializationUtils.RawSerialize(record);
		if (ConstantRecordSize.HasValue && array.Length != ConstantRecordSize.Value)
		{
			throw new ExceptionBtrieve(Error.B_DATALENGTH_ERROR, FilePath, OperationCode.B_UPDATE);
		}
		int dataLength = array.Length;
		byte[] array2 = new byte[2];
		Error error = BtrieveInterface.BtrieveOperation(OperationCode.B_UPDATE, Position, array, ref dataLength, array2, (byte)array2.Length, 0);
		if (error != Error.B_NO_ERROR)
		{
			throw new ExceptionBtrieve(error, FilePath, OperationCode.B_UPDATE);
		}
	}

	public void DeleteRecord()
	{
		int dataLength = 0;
		byte[] array = new byte[2];
		Error error = BtrieveInterface.BtrieveOperation(OperationCode.B_DELETE, Position, null, ref dataLength, array, (byte)array.Length, 0);
		if (error != Error.B_NO_ERROR)
		{
			throw new ExceptionBtrieve(error, FilePath, OperationCode.B_DELETE);
		}
	}
}
