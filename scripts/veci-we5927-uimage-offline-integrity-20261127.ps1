# WE5927 legacy U-Boot uImage CRC verification - OFFLINE WINDOWS FILES ONLY
# No SSH, router access, firmware upload, flash, reboot, or restore attempt.
[CmdletBinding()]
param(
  [string]$ImagePath='D:\Report_CCB\WE5927-CURRENT-MTD3-RAW-NOT-FLASHABLE-20261127_122757.bin',
  [string]$ReceiptPath='D:\Report_CCB\WE5927-CURRENT-MTD3-RAW-NOT-FLASHABLE-20261127_122757.json'
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if(!(Test-Path -LiteralPath $ImagePath -PathType Leaf)){throw 'STOP=RAW_IMAGE_NOT_FOUND'}
if(!(Test-Path -LiteralPath $ReceiptPath -PathType Leaf)){throw 'STOP=BACKUP_RECEIPT_NOT_FOUND'}
$receipt=Get-Content -LiteralPath $ReceiptPath -Raw | ConvertFrom-Json
if($receipt.schema -ne 'we5927-readonly-current-mtd3-backup.v1' -or
    $receipt.image_kind -ne 'RAW_MTD3_NOT_A_SYSUPGRADE_IMAGE' -or
    $receipt.board -ne 'zbtlink,zbt-we5927' -or
    $receipt.firmware_flash_authorized -ne $false -or
    $receipt.remote_hash_before_match -ne $true -or
    $receipt.remote_hash_after_match -ne $true){
  throw 'STOP=BACKUP_RECEIPT_NOT_VERIFIED'
}
$realPath=[System.IO.Path]::GetFullPath((Resolve-Path -LiteralPath $ImagePath).Path)
$claimedPath=[System.IO.Path]::GetFullPath([string]$receipt.image_path)
if(-not [string]::Equals($realPath,$claimedPath,[System.StringComparison]::OrdinalIgnoreCase)){
  throw 'STOP=BACKUP_RECEIPT_IMAGE_PATH_MISMATCH'
}
$expectedBytes=[long]7995392
if([long]$receipt.bytes -ne $expectedBytes -or (Get-Item -LiteralPath $realPath).Length -ne $expectedBytes){
  throw 'STOP=BACKUP_LENGTH_MISMATCH'
}
if([string]$receipt.sha256 -notmatch '^[0-9a-fA-F]{64}$'){throw 'STOP=BACKUP_RECEIPT_SHA256_INVALID'}
$actualSha=(Get-FileHash -LiteralPath $realPath -Algorithm SHA256).Hash.ToLowerInvariant()
if($actualSha -ne ([string]$receipt.sha256).ToLowerInvariant()){throw 'STOP=RAW_IMAGE_SHA256_MISMATCH'}
Write-Output 'LOCAL_BACKUP_AND_RECEIPT_SHA256=PASS'
Write-Output 'ROUTER_ACCESS=NONE; FLASH=NO; REBOOT=NO; RECOVERY=NOT_TESTED'

# C# type is constant trusted code bundled in this SHA-pinned script. No dynamic user code.
Add-Type -Language CSharp -TypeDefinition @'
using System;
using System.IO;
public static class VeCIWe5927LegacyUimageCrc
{
    public static UInt32 Be32(byte[] b, int off)
    {
        return ((UInt32)b[off] << 24) | ((UInt32)b[off+1] << 16) |
               ((UInt32)b[off+2] << 8) | b[off+3];
    }
    private static readonly UInt32[] Table = BuildTable();
    private static UInt32[] BuildTable()
    {
        var table = new UInt32[256];
        for (UInt32 n=0; n<256; n++)
        {
            UInt32 c=n;
            for (int bit=0;bit<8;bit++)
                c = (c & 1U)!=0U ? 0xEDB88320U ^ (c >> 1) : c >> 1;
            table[n]=c;
        }
        return table;
    }
    public static UInt32 Crc(byte[] bytes, int count)
    {
        UInt32 state=0xFFFFFFFFU;
        for(int i=0;i<count;i++)
            state=Table[(state ^ bytes[i]) & 0xFFU] ^ (state >> 8);
        return state ^ 0xFFFFFFFFU;
    }
    public static UInt32 CrcRange(Stream src, long start, long length)
    {
        if (length<0 || start<0 || start>src.Length || length>src.Length-start)
            throw new InvalidDataException("CRC_RANGE_OUT_OF_BOUNDS");
        src.Seek(start,SeekOrigin.Begin);
        byte[] buffer = new byte[65536];
        UInt32 state=0xFFFFFFFFU;
        while(length>0)
        {
            int requested=(int)Math.Min(buffer.Length,length);
            int count=src.Read(buffer,0,requested);
            if(count<=0) throw new EndOfStreamException("CRC_UNEXPECTED_EOF");
            for(int i=0;i<count;i++)
                state=Table[(state ^ buffer[i]) & 0xFFU] ^ (state >> 8);
            length-=count;
        }
        return state ^ 0xFFFFFFFFU;
    }
    public static string[] Inspect(string path, long exactPartitionBytes)
    {
        using(var stream = new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.Read))
        {
            if(stream.Length!=exactPartitionBytes) throw new InvalidDataException("BAD_PARTITION_LENGTH");
            byte[] header=new byte[64];
            int received=0;
            while(received<64)
            {
                int n=stream.Read(header,received,64-received);
                if(n<=0) throw new EndOfStreamException("HEADER_TOO_SHORT");
                received+=n;
            }
            UInt32 magic=Be32(header,0);
            if(magic!=0x27051956U) throw new InvalidDataException("BAD_UIMAGE_MAGIC");
            UInt32 headerExpected=Be32(header,4);
            UInt32 length=Be32(header,12);
            UInt32 dataExpected=Be32(header,24);
            if(length==0U || (long)length>stream.Length-64)
                throw new InvalidDataException("BAD_UIMAGE_PAYLOAD_BOUNDS");
            header[4]=header[5]=header[6]=header[7]=0;
            UInt32 headerActual=Crc(header,64);
            UInt32 dataActual=CrcRange(stream,64,(long)length);
            byte os=header[28], arch=header[29], type=header[30], comp=header[31];
            string meta=(os==5 && arch==5 && type==2) ? "LINUX_MIPS_KERNEL" : "NONSTANDARD_OS_ARCH_TYPE";
            return new string[]{
                "UIMAGE_MAGIC=27051956",
                "UIMAGE_PAYLOAD_BYTES="+length.ToString(),
                "UIMAGE_TOTAL_BYTES="+(64L+length).ToString(),
                "UIMAGE_HEADER_CRC32_EXPECTED="+headerExpected.ToString("x8"),
                "UIMAGE_HEADER_CRC32_COMPUTED="+headerActual.ToString("x8"),
                "UIMAGE_HEADER_CRC32="+(headerExpected==headerActual?"PASS":"FAIL"),
                "UIMAGE_DATA_CRC32_EXPECTED="+dataExpected.ToString("x8"),
                "UIMAGE_DATA_CRC32_COMPUTED="+dataActual.ToString("x8"),
                "UIMAGE_DATA_CRC32="+(dataExpected==dataActual?"PASS":"FAIL"),
                "UIMAGE_OS_CODE="+os.ToString(),
                "UIMAGE_ARCH_CODE="+arch.ToString(),
                "UIMAGE_TYPE_CODE="+type.ToString(),
                "UIMAGE_COMPRESSION_CODE="+comp.ToString(),
                "UIMAGE_METADATA="+meta
            };
        }
    }
}
'@
$result=@([VeCIWe5927LegacyUimageCrc]::Inspect($realPath,$expectedBytes))
foreach($line in $result){Write-Output $line}
if($result -notcontains 'UIMAGE_HEADER_CRC32=PASS'){
  throw 'STOP=UIMAGE_HEADER_CRC32_MISMATCH'
}
if($result -notcontains 'UIMAGE_DATA_CRC32=PASS'){
  throw 'STOP=UIMAGE_DATA_CRC32_MISMATCH'
}
Write-Output 'UIMAGE_LEGACY_CHECKSUMS=PASS'
Write-Output 'BOOTLOADER_RESTORE_FORMAT=NOT_VERIFIED'
Write-Output 'RAW_MTD3_NOT_FLASHABLE=YES; ROUTER_NOT_CONTACTED=YES'
