namespace OtxDataBaseLayer.Database.BtrieveAPI;

public abstract class BtrieveFileBase
{
	public bool ReadOnly;

	public abstract void Open(string path = null);

	public abstract void Close();

	public abstract RECORD_TYPE Read<RECORD_TYPE>(OperationCode operationCode, object key);
}
