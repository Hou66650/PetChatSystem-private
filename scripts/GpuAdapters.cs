using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

// DXGI 1.1 enumeration: fresh factory each launch, never persist adapter LUIDs.
public static class PaitGpuAdapters {
    [StructLayout(LayoutKind.Sequential)] public struct Luid { public uint Low; public int High; }
    [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)] public struct Desc {
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst=128)] public string Name;
        public uint Vendor, Device, Subsystem, Revision;
        public UIntPtr VideoMemory, SystemMemory, SharedMemory;
        public Luid Id;
        public uint Flags;
    }
    public class Adapter { public string Name, Luid; public uint Vendor, Device; public ulong VideoMemory; }
    [DllImport("dxgi.dll")] static extern int CreateDXGIFactory1(ref Guid iid, out IntPtr factory);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int Enumerate(IntPtr self, uint index, out IntPtr adapter);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int Describe(IntPtr self, out Desc desc);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate uint Release(IntPtr self);
    static Delegate Method(IntPtr instance, int slot, Type type) {
        return Marshal.GetDelegateForFunctionPointer(Marshal.ReadIntPtr(Marshal.ReadIntPtr(instance), slot * IntPtr.Size), type);
    }
    public static Adapter[] Read() {
        var iid = new Guid("770aae78-f26f-4dba-a829-253c83d1b387");
        IntPtr factory;
        Marshal.ThrowExceptionForHR(CreateDXGIFactory1(ref iid, out factory));
        var rows = new List<Adapter>();
        try {
            var enumerate = (Enumerate)Method(factory, 12, typeof(Enumerate));
            for(uint index=0; ; index++) {
                IntPtr adapter;
                int hr = enumerate(factory, index, out adapter);
                if (unchecked((uint)hr) == 0x887A0002) break; // DXGI_ERROR_NOT_FOUND
                Marshal.ThrowExceptionForHR(hr);
                try {
                    Desc desc;
                    Marshal.ThrowExceptionForHR(((Describe)Method(adapter, 10, typeof(Describe)))(adapter, out desc));
                    if ((desc.Flags & 2) == 0) rows.Add(new Adapter {
                        Name=desc.Name, Vendor=desc.Vendor, Device=desc.Device,
                        VideoMemory=desc.VideoMemory.ToUInt64(), Luid=desc.Id.High + "," + desc.Id.Low
                    });
                } finally { ((Release)Method(adapter, 2, typeof(Release)))(adapter); }
            }
        } finally { ((Release)Method(factory, 2, typeof(Release)))(factory); }
        return rows.ToArray();
    }
}
