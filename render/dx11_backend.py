# ---- Primitive queueing API (to be flushed in end_scene) ----
# DX11 + DirectComposition backend scaffolding using comtypes
# This module intentionally starts minimal and non-destructive.
# It provides a safe initialization path that will gracefully fail and
# allow callers to fall back to the GDI delegate until full DX is wired.

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict
import ctypes
from ctypes import wintypes

try:
    import comtypes  # type: ignore
    from comtypes import GUID  # type: ignore
    from comtypes import IUnknown  # type: ignore
    from comtypes import HRESULT  # type: ignore
    from comtypes import POINTER  # type: ignore
    from comtypes.automation import IDispatch  # type: ignore
    from comtypes import COMMETHOD  # type: ignore
    COMTYPES_AVAILABLE = True
except Exception:
    COMTYPES_AVAILABLE = False


@dataclass
class DXContext:
    hwnd: int
    width: int
    height: int
    # Placeholders for future COM objects
    d3d_device: Optional[object] = None
    d3d_context: Optional[object] = None
    dxgi_swapchain: Optional[object] = None
    dcomp_device: Optional[object] = None
    dcomp_target: Optional[object] = None
    dcomp_visual: Optional[object] = None
    # State flags
    ready: bool = False
    # Render targets
    rtv: Optional[object] = None
    # Queues for primitives (CPU-side for now)
    q_lines: List[Tuple[float, float, float, float, Tuple[int, int, int, int]]] = None  # (x1,y1,x2,y2,rgba)
    q_rects: List[Tuple[float, float, float, float, Tuple[int, int, int, int], bool]] = None  # (x,y,w,h,rgba,filled)
    q_circles: List[Tuple[float, float, float, Tuple[int, int, int, int], bool]] = None  # (x,y,r,rgba,filled)
    q_texts: List[Tuple[str, float, float, Tuple[int, int, int, int], int, bool]] = None  # (text,x,y,rgba,size,centered)
    # Pipeline resources
    vs: Optional[object] = None
    ps: Optional[object] = None
    layout: Optional[object] = None
    vbuf: Optional[object] = None
    vbuf_capacity: int = 0
    blend: Optional[object] = None
    # Text pipeline/resources
    vs_text: Optional[object] = None
    ps_text: Optional[object] = None
    layout_text: Optional[object] = None
    sampler: Optional[object] = None
    font_tex: Optional[object] = None
    font_srv: Optional[object] = None
    glyphs: Optional[Dict[str, Tuple[float,float,float,float,int,int,int]]] = None  # u0,v0,u1,v1,ox,oy,adv
    font_size_px: int = 14
    _atlas_w: int = 0
    _atlas_h: int = 0


# --- Minimal COM interface and struct definitions for DXGI & DComp ---
if COMTYPES_AVAILABLE:
    # DXGI format and flags
    DXGI_FORMAT_B8G8R8A8_UNORM = 87
    DXGI_USAGE_RENDER_TARGET_OUTPUT = 0x00000020
    DXGI_SCALING_STRETCH = 0
    DXGI_SWAP_EFFECT_FLIP_SEQUENTIAL = 3
    DXGI_ALPHA_MODE_PREMULTIPLIED = 1

    class DXGI_SAMPLE_DESC(ctypes.Structure):
        _fields_ = [("Count", ctypes.c_uint), ("Quality", ctypes.c_uint)]

    class DXGI_SWAP_CHAIN_DESC1(ctypes.Structure):
        _fields_ = [
            ("Width", ctypes.c_uint),
            ("Height", ctypes.c_uint),
            ("Format", ctypes.c_uint),
            ("Stereo", ctypes.c_int),
            ("SampleDesc", DXGI_SAMPLE_DESC),
            ("BufferUsage", ctypes.c_uint),
            ("BufferCount", ctypes.c_uint),
            ("Scaling", ctypes.c_uint),
            ("SwapEffect", ctypes.c_uint),
            ("AlphaMode", ctypes.c_uint),
            ("Flags", ctypes.c_uint),
        ]

    # D3DCompiler support: ID3DBlob for shader bytecode
    class ID3DBlob(IUnknown):
        _iid_ = GUID("8BA5FB08-5195-40e2-AC58-0D989C3A0102")
        _methods_ = [
            COMMETHOD([], ctypes.c_void_p, "GetBufferPointer"),
            COMMETHOD([], ctypes.c_size_t, "GetBufferSize"),
        ]

    # Minimal DXGI_FORMAT and input element descriptors
    DXGI_FORMAT_R32G32_FLOAT = 16
    DXGI_FORMAT_R32G32B32A32_FLOAT = 2
    D3D11_INPUT_PER_VERTEX_DATA = 0
    class D3D11_INPUT_ELEMENT_DESC(ctypes.Structure):
        _fields_ = [
            ("SemanticName", ctypes.c_char_p),
            ("SemanticIndex", ctypes.c_uint),
            ("Format", ctypes.c_uint),
            ("InputSlot", ctypes.c_uint),
            ("AlignedByteOffset", ctypes.c_uint),
            ("InputSlotClass", ctypes.c_uint),
            ("InstanceDataStepRate", ctypes.c_uint),
        ]
    # Blend descriptors
    class D3D11_RENDER_TARGET_BLEND_DESC(ctypes.Structure):
        _fields_ = [
            ("BlendEnable", ctypes.c_uint),
            ("SrcBlend", ctypes.c_uint),
            ("DestBlend", ctypes.c_uint),
            ("BlendOp", ctypes.c_uint),
            ("SrcBlendAlpha", ctypes.c_uint),
            ("DestBlendAlpha", ctypes.c_uint),
            ("BlendOpAlpha", ctypes.c_uint),
            ("RenderTargetWriteMask", ctypes.c_uint),
        ]
    class D3D11_BLEND_DESC(ctypes.Structure):
        _fields_ = [
            ("AlphaToCoverageEnable", ctypes.c_uint),
            ("IndependentBlendEnable", ctypes.c_uint),
            ("RenderTarget", D3D11_RENDER_TARGET_BLEND_DESC * 8),
        ]
    # Enums used
    D3D11_BLEND_ONE = 1
    D3D11_BLEND_INV_SRC_ALPHA = 6
    D3D11_BLEND_OP_ADD = 1
    D3D11_COLOR_WRITE_ENABLE_ALL = 0x0F
    # Texture/sampler structures
    class D3D11_TEXTURE2D_DESC(ctypes.Structure):
        _fields_ = [
            ("Width", ctypes.c_uint), ("Height", ctypes.c_uint), ("MipLevels", ctypes.c_uint), ("ArraySize", ctypes.c_uint),
            ("Format", ctypes.c_uint), ("SampleDesc", ctypes.c_uint * 2), ("Usage", ctypes.c_uint), ("BindFlags", ctypes.c_uint),
            ("CPUAccessFlags", ctypes.c_uint), ("MiscFlags", ctypes.c_uint)
        ]
    class D3D11_SUBRESOURCE_DATA(ctypes.Structure):
        _fields_ = [("pSysMem", ctypes.c_void_p), ("SysMemPitch", ctypes.c_uint), ("SysMemSlicePitch", ctypes.c_uint)]
    class D3D11_SAMPLER_DESC(ctypes.Structure):
        _fields_ = [
            ("Filter", ctypes.c_uint), ("AddressU", ctypes.c_uint), ("AddressV", ctypes.c_uint), ("AddressW", ctypes.c_uint),
            ("MipLODBias", ctypes.c_float), ("MaxAnisotropy", ctypes.c_uint), ("ComparisonFunc", ctypes.c_uint),
            ("BorderColor", ctypes.c_float * 4), ("MinLOD", ctypes.c_float), ("MaxLOD", ctypes.c_float)
        ]
    # Enums
    DXGI_FORMAT_R8G8B8A8_UNORM = 28
    D3D11_USAGE_IMMUTABLE = 0
    D3D11_BIND_SHADER_RESOURCE = 0x8
    D3D11_FILTER_MIN_MAG_MIP_LINEAR = 0x15
    D3D11_TEXTURE_ADDRESS_CLAMP = 3
    D3D11_COMPARISON_ALWAYS = 8

    # Forward declarations
    class IDXGIDevice(IUnknown):
        _iid_ = GUID("77db970f-6276-48ba-ba28-070143b4392c")
        _methods_ = []

    class IDXGISwapChain1(IUnknown):
        _iid_ = GUID("790a45f7-0d42-4876-983a-0a55cfe6f4aa")
        _methods_ = [
            # We only declare Present for our use
            COMMETHOD([], HRESULT, "Present",
                      (['in'], ctypes.c_uint, "SyncInterval"),
                      (['in'], ctypes.c_uint, "Flags")),
            COMMETHOD([], HRESULT, "GetBuffer",
                      (['in'], ctypes.c_uint, "Buffer"),
                      (['in'], ctypes.POINTER(GUID), "riid"),
                      (['out'], ctypes.POINTER(ctypes.c_void_p), "ppSurface")),
        ]

    class IDXGIFactory2(IUnknown):
        _iid_ = GUID("50c83a1c-e072-4c48-87b0-3630fa36a6d0")
        _methods_ = [
            COMMETHOD([], HRESULT, "CreateSwapChainForHwnd",
                      (['in'], POINTER(IUnknown), "pDevice"),
                      (['in'], wintypes.HWND, "hWnd"),
                      (['in'], ctypes.POINTER(DXGI_SWAP_CHAIN_DESC1), "pDesc"),
                      (['in'], ctypes.c_void_p, "pFullscreenDesc"),
                      (['in'], ctypes.c_void_p, "pRestrictToOutput"),
                      (['out'], ctypes.POINTER(POINTER(IDXGISwapChain1)), "ppSwapChain")),
        ]

    class ID3D11Device(IUnknown):
        _iid_ = GUID("db6f6ddb-ac77-4e88-8253-819df9bbf140")
        _methods_ = [
            COMMETHOD([], HRESULT, "CreateRenderTargetView",
                      (['in'], POINTER(IUnknown), "pResource"),
                      (['in'], ctypes.c_void_p, "pDesc"),
                      (['out'], ctypes.POINTER(POINTER(IUnknown)), "ppRTView")),
            COMMETHOD([], HRESULT, "CreateBuffer",
                      (['in'], ctypes.c_void_p, "pDesc"),
                      (['in'], ctypes.c_void_p, "pInitialData"),
                      (['out'], ctypes.POINTER(ctypes.c_void_p), "ppBuffer")),
            COMMETHOD([], HRESULT, "CreateVertexShader",
                      (['in'], ctypes.c_void_p, "pShaderBytecode"),
                      (['in'], ctypes.c_size_t, "BytecodeLength"),
                      (['in'], ctypes.c_void_p, "pClassLinkage"),
                      (['out'], ctypes.POINTER(ctypes.c_void_p), "ppVertexShader")),
            COMMETHOD([], HRESULT, "CreatePixelShader",
                      (['in'], ctypes.c_void_p, "pShaderBytecode"),
                      (['in'], ctypes.c_size_t, "BytecodeLength"),
                      (['in'], ctypes.c_void_p, "pClassLinkage"),
                      (['out'], ctypes.POINTER(ctypes.c_void_p), "ppPixelShader")),
            COMMETHOD([], HRESULT, "CreateInputLayout",
                      (['in'], ctypes.c_void_p, "pInputElementDescs"),
                      (['in'], ctypes.c_uint, "NumElements"),
                      (['in'], ctypes.c_void_p, "pShaderBytecodeWithInputSignature"),
                      (['in'], ctypes.c_size_t, "BytecodeLength"),
                      (['out'], ctypes.POINTER(ctypes.c_void_p), "ppInputLayout")),
            COMMETHOD([], HRESULT, "CreateBlendState",
                      (['in'], ctypes.c_void_p, "pBlendStateDesc"),
                      (['out'], ctypes.POINTER(ctypes.c_void_p), "ppBlendState")),
            COMMETHOD([], HRESULT, "CreateTexture2D",
                      (['in'], ctypes.c_void_p, "pDesc"),
                      (['in'], ctypes.c_void_p, "pInitialData"),
                      (['out'], ctypes.POINTER(ctypes.c_void_p), "ppTexture2D")),
            COMMETHOD([], HRESULT, "CreateShaderResourceView",
                      (['in'], ctypes.c_void_p, "pResource"),
                      (['in'], ctypes.c_void_p, "pDesc"),
                      (['out'], ctypes.POINTER(ctypes.c_void_p), "ppSRView")),
            COMMETHOD([], HRESULT, "CreateSamplerState",
                      (['in'], ctypes.c_void_p, "pSamplerDesc"),
                      (['out'], ctypes.POINTER(ctypes.c_void_p), "ppSamplerState")),
        ]

    class ID3D11DeviceContext(IUnknown):
        _iid_ = GUID("c0bfa96c-e089-44fb-8eaf-26f8796190da")
        _methods_ = [
            COMMETHOD([], None, "OMSetRenderTargets",
                      (['in'], ctypes.c_uint, "NumViews"),
                      (['in'], ctypes.POINTER(POINTER(IUnknown)), "ppRenderTargetViews"),
                      (['in'], ctypes.c_void_p, "pDepthStencilView")),
            COMMETHOD([], None, "ClearRenderTargetView",
                      (['in'], POINTER(IUnknown), "pRenderTargetView"),
                      (['in'], ctypes.c_float * 4, "ColorRGBA")),
            COMMETHOD([], None, "IASetInputLayout",
                      (['in'], ctypes.c_void_p, "pInputLayout")),
            COMMETHOD([], None, "IASetPrimitiveTopology",
                      (['in'], ctypes.c_uint, "Topology")),
            COMMETHOD([], None, "IASetVertexBuffers",
                      (['in'], ctypes.c_uint, "StartSlot"),
                      (['in'], ctypes.c_uint, "NumBuffers"),
                      (['in'], ctypes.POINTER(ctypes.c_void_p), "ppVertexBuffers"),
                      (['in'], ctypes.POINTER(ctypes.c_uint), "pStrides"),
                      (['in'], ctypes.POINTER(ctypes.c_uint), "pOffsets")),
            COMMETHOD([], None, "VSSetShader",
                      (['in'], ctypes.c_void_p, "pVertexShader"),
                      (['in'], ctypes.c_void_p, "ppClassInstances"),
                      (['in'], ctypes.c_uint, "NumClassInstances")),
            COMMETHOD([], None, "PSSetShader",
                      (['in'], ctypes.c_void_p, "pPixelShader"),
                      (['in'], ctypes.c_void_p, "ppClassInstances"),
                      (['in'], ctypes.c_uint, "NumClassInstances")),
            COMMETHOD([], None, "OMSetBlendState",
                      (['in'], ctypes.c_void_p, "pBlendState"),
                      (['in'], ctypes.c_float * 4, "BlendFactor"),
                      (['in'], ctypes.c_uint, "SampleMask")),
            COMMETHOD([], None, "Draw",
                      (['in'], ctypes.c_uint, "VertexCount"),
                      (['in'], ctypes.c_uint, "StartVertexLocation")),
            COMMETHOD([], None, "PSSetShaderResources",
                      (['in'], ctypes.c_uint, "StartSlot"),
                      (['in'], ctypes.c_uint, "NumViews"),
                      (['in'], ctypes.POINTER(ctypes.c_void_p), "ppShaderResourceViews")),
            COMMETHOD([], None, "PSSetSamplers",
                      (['in'], ctypes.c_uint, "StartSlot"),
                      (['in'], ctypes.c_uint, "NumSamplers"),
                      (['in'], ctypes.POINTER(ctypes.c_void_p), "ppSamplers")),
        ]

    # DirectComposition
    class IDCompositionDevice(IUnknown):
        _iid_ = GUID("c37ea93a-e7aa-450d-b16f-9746cb0407f3")
        _methods_ = [
            COMMETHOD([], HRESULT, "CreateTargetForHwnd",
                      (['in'], wintypes.HWND, "hwnd"),
                      (['in'], ctypes.c_int, "topmost"),
                      (['out'], ctypes.POINTER(POINTER(IUnknown)), "target")),
            COMMETHOD([], HRESULT, "CreateVisual",
                      (['out'], ctypes.POINTER(POINTER(IUnknown)), "visual")),
            COMMETHOD([], HRESULT, "Commit"),
        ]

    class IDCompositionTarget(IUnknown):
        _iid_ = GUID("eacdd04c-117e-4e17-88f4-d1b12b0e3d89")
        _methods_ = [
            COMMETHOD([], HRESULT, "SetRoot",
                      (['in'], POINTER(IUnknown), "visual")),
        ]

    class IDCompositionVisual(IUnknown):
        _iid_ = GUID("4d93059d-097b-4651-9a60-f0f2e3eeea85")
        _methods_ = [
            COMMETHOD([], HRESULT, "SetContent",
                      (['in'], POINTER(IUnknown), "content")),
        ]


def initialize(hwnd: int, width: int, height: int) -> Optional[DXContext]:
    """
    Step 1: Attempt to create a D3D11 device/context using D3D11CreateDevice via ctypes.
    Swapchain + DirectComposition wiring will be added next.
    Returns DXContext on success, or None on failure. No exceptions escape.
    """
    try:
        # Load d3d11.dll
        d3d11 = ctypes.WinDLL('d3d11.dll')

        # D3D11 constants
        D3D_DRIVER_TYPE_HARDWARE = 1
        D3D_DRIVER_TYPE_WARP = 5
        D3D_DRIVER_TYPE_REFERENCE = 4
        D3D11_CREATE_DEVICE_BGRA_SUPPORT = 0x20
        D3D11_SDK_VERSION = 7

        # Prepare out pointers
        ppDevice = ctypes.c_void_p()
        ppImmediateContext = ctypes.c_void_p()
        pFeatureLevel = ctypes.c_uint()

        # Prototype: HRESULT D3D11CreateDevice(
        #   IDXGIAdapter* pAdapter,
        #   D3D_DRIVER_TYPE DriverType,
        #   HMODULE Software,
        #   UINT Flags,
        #   const D3D_FEATURE_LEVEL* pFeatureLevels,
        #   UINT FeatureLevels,
        #   UINT SDKVersion,
        #   ID3D11Device** ppDevice,
        #   D3D_FEATURE_LEVEL* pFeatureLevel,
        #   ID3D11DeviceContext** ppImmediateContext)
        D3D11CreateDevice = d3d11.D3D11CreateDevice
        D3D11CreateDevice.argtypes = [
            ctypes.c_void_p,  # IDXGIAdapter*
            ctypes.c_uint,    # D3D_DRIVER_TYPE
            wintypes.HMODULE, # Software
            ctypes.c_uint,    # Flags
            ctypes.POINTER(ctypes.c_uint),  # pFeatureLevels
            ctypes.c_uint,    # FeatureLevels count
            ctypes.c_uint,    # SDKVersion
            ctypes.POINTER(ctypes.c_void_p),  # ID3D11Device**
            ctypes.POINTER(ctypes.c_uint),    # D3D_FEATURE_LEVEL*
            ctypes.POINTER(ctypes.c_void_p),  # ID3D11DeviceContext**
        ]
        D3D11CreateDevice.restype = ctypes.c_long  # HRESULT

        def try_create(driver_type: int) -> bool:
            nonlocal ppDevice, ppImmediateContext, pFeatureLevel
            hr = D3D11CreateDevice(
                None,
                driver_type,
                None,
                D3D11_CREATE_DEVICE_BGRA_SUPPORT,
                None,  # Let D3D choose highest available feature level
                0,
                D3D11_SDK_VERSION,
                ctypes.byref(ppDevice),
                ctypes.byref(pFeatureLevel),
                ctypes.byref(ppImmediateContext),
            )
            return hr >= 0 and bool(ppDevice.value) and bool(ppImmediateContext.value)

        # Try hardware -> WARP -> REF
        created = (
            try_create(D3D_DRIVER_TYPE_HARDWARE)
            or try_create(D3D_DRIVER_TYPE_WARP)
            or try_create(D3D_DRIVER_TYPE_REFERENCE)
        )

        if not created:
            return None

        ctx = DXContext(hwnd=hwnd, width=width, height=height)
        ctx.d3d_device = ppDevice
        ctx.d3d_context = ppImmediateContext
        # Try to create swapchain + DirectComposition. Keep safe on failure.
        try:
            _setup_swapchain_and_composition(ctx)
        except Exception:
            pass
        # Flip ready once swapchain and composition exist; begin/end will clear and present safely.
        ctx.ready = bool(ctx.dxgi_swapchain) and bool(ctx.dcomp_device) and bool(ctx.rtv)
        # Initialize primitive queues
        ctx.q_lines = []
        ctx.q_rects = []
        ctx.q_circles = []
        ctx.q_texts = []
        # Initialize shader pipeline
        try:
            _setup_pipeline(ctx)
        except Exception:
            pass
        # Setup text pipeline and atlas lazily in first text draw; can also prebuild default here
        try:
            _setup_text_pipeline(ctx)
            _ensure_font_atlas(ctx, None, ctx.font_size_px)
        except Exception:
            pass
        return ctx
    except Exception:
        return None


def begin_scene(ctx: DXContext) -> bool:
    """
    Prepare a frame. Returns True if GPU path is ready.
    """
    if ctx is None or not ctx.ready or ctx.dxgi_swapchain is None:
        return False
    try:
        # Reset per-frame queues
        ctx.q_lines.clear()
        ctx.q_rects.clear()
        ctx.q_circles.clear()
        ctx.q_texts.clear()
        # Bind RTV and clear to transparent
        devctx = ctypes.cast(ctx.d3d_context, POINTER(ID3D11DeviceContext))
        rtv_ptr = ctypes.cast(ctx.rtv, POINTER(ID3D11RenderTargetView))
        arr = (POINTER(ID3D11RenderTargetView) * 1)(rtv_ptr)
        devctx.OMSetRenderTargets(1, arr, None)
        clear = (ctypes.c_float * 4)(0.0, 0.0, 0.0, 0.0)
        devctx.ClearRenderTargetView(rtv_ptr, clear)
        return True
    except Exception:
        return False


def end_scene(ctx: DXContext) -> bool:
    """
    Present a frame and commit composition. Returns True if successful.
    """
    if ctx is None or not ctx.ready or ctx.dxgi_swapchain is None:
        return False
    try:
        # Flush queued primitives with GPU draws
        try:
            _flush_primitives(ctx)
        except Exception:
            pass
        # Present without vsync (SyncInterval=0) to avoid 60Hz cap; the caller may pace frames.
        sc = ctypes.cast(ctx.dxgi_swapchain, POINTER(IDXGISwapChain1))
        hr = sc.Present(0, 0)
        if hr < 0:
            return False
        dcomp_dev = ctypes.cast(ctx.dcomp_device, POINTER(IDCompositionDevice))
        hr2 = dcomp_dev.Commit()
        return hr2 >= 0
    except Exception:
        return False


def _setup_swapchain_and_composition(ctx: DXContext) -> None:
    """
    Scaffolding for creating a DXGI flip-model swapchain and a DirectComposition
    visual tree attached to the given HWND. This function is intentionally
    defensive; if COM types are not available, it will safely no-op.
    """
    if not COMTYPES_AVAILABLE:
        return
    # Load function entry points
    dxgi = ctypes.WinDLL('dxgi.dll')
    dcomp = ctypes.WinDLL('dcomp.dll')

    # HRESULT CreateDXGIFactory2(UINT Flags, REFIID riid, void **ppFactory)
    CreateDXGIFactory2 = dxgi.CreateDXGIFactory2
    CreateDXGIFactory2.argtypes = [ctypes.c_uint, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)]
    CreateDXGIFactory2.restype = ctypes.c_long

    # HRESULT DCompositionCreateDevice(IUnknown* renderingDevice, REFIID iid, void** dcompositionDevice)
    DCompositionCreateDevice = dcomp.DCompositionCreateDevice
    DCompositionCreateDevice.argtypes = [ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)]
    DCompositionCreateDevice.restype = ctypes.c_long

    # Create DXGI Factory2
    pFactory = ctypes.c_void_p()
    iid_factory2 = IDXGIFactory2._iid_
    hr = CreateDXGIFactory2(0, ctypes.byref(iid_factory2), ctypes.byref(pFactory))
    if hr < 0 or not pFactory.value:
        return

    # Prepare swapchain desc
    desc = DXGI_SWAP_CHAIN_DESC1()
    desc.Width = ctx.width
    desc.Height = ctx.height
    desc.Format = DXGI_FORMAT_B8G8R8A8_UNORM
    desc.Stereo = 0
    desc.SampleDesc = DXGI_SAMPLE_DESC(1, 0)
    desc.BufferUsage = DXGI_USAGE_RENDER_TARGET_OUTPUT
    desc.BufferCount = 2
    desc.Scaling = DXGI_SCALING_STRETCH
    desc.SwapEffect = DXGI_SWAP_EFFECT_FLIP_SEQUENTIAL
    desc.AlphaMode = DXGI_ALPHA_MODE_PREMULTIPLIED
    desc.Flags = 0

    # Cast factory to COM and create swapchain for HWND
    factory = ctypes.cast(pFactory, POINTER(IDXGIFactory2))
    device_as_unknown = ctypes.cast(ctx.d3d_device, POINTER(IUnknown))
    hwnd = wintypes.HWND(ctx.hwnd)
    pSwap = ctypes.POINTER(IDXGISwapChain1)()
    hr2 = factory.CreateSwapChainForHwnd(device_as_unknown, hwnd, ctypes.byref(desc), None, None, ctypes.byref(pSwap))
    if hr2 < 0 or not pSwap:
        return

    # Create RTV from back buffer 0
    backbuffer = ctypes.c_void_p()
    iid_tex2d = ID3D11Texture2D._iid_
    hrbb = pSwap.GetBuffer(0, ctypes.byref(iid_tex2d), ctypes.byref(backbuffer))
    if hrbb < 0 or not backbuffer.value:
        return

    d3d_device = ctypes.cast(ctx.d3d_device, POINTER(ID3D11Device))
    pRTV = ctypes.POINTER(ID3D11RenderTargetView)()
    hr_rtv = d3d_device.CreateRenderTargetView(ctypes.cast(backbuffer, POINTER(ID3D11Resource)), None, ctypes.byref(pRTV))
    if hr_rtv < 0 or not pRTV:
        return

    # Create DirectComposition device using DXGI device (from D3D11 device)
    # Query ID3D11Device -> IDXGIDevice (or 1)
    try:
        dxgi_device = device_as_unknown.QueryInterface(IDXGIDevice)
    except Exception:
        # Try IDXGIDevice1 if first fails
        dxgi_device = device_as_unknown.QueryInterface(IDXGIDevice)

    pDCompDev = ctypes.c_void_p()
    iid_dcomp = IDCompositionDevice._iid_
    hr3 = DCompositionCreateDevice(ctypes.cast(dxgi_device, ctypes.c_void_p), ctypes.byref(iid_dcomp), ctypes.byref(pDCompDev))
    if hr3 < 0 or not pDCompDev.value:
        return

    dcomp_device = ctypes.cast(pDCompDev, POINTER(IDCompositionDevice))

    # Create target and visual
    pTargetUnknown = ctypes.POINTER(IUnknown)()
    hr4 = dcomp_device.CreateTargetForHwnd(hwnd, 1, ctypes.byref(pTargetUnknown))
    if hr4 < 0 or not pTargetUnknown:
        return
    target = pTargetUnknown.QueryInterface(IDCompositionTarget)

    pVisualUnknown = ctypes.POINTER(IUnknown)()
    hr5 = dcomp_device.CreateVisual(ctypes.byref(pVisualUnknown))
    if hr5 < 0 or not pVisualUnknown:
        return
    visual = pVisualUnknown.QueryInterface(IDCompositionVisual)

    # Set swapchain as content
    hr6 = visual.SetContent(pSwap)
    if hr6 < 0:
        return
    # Set root visual and commit
    hr7 = target.SetRoot(visual)
    if hr7 < 0:
        return
    hr8 = dcomp_device.Commit()
    if hr8 < 0:
        return

    # Store in context
    ctx.dxgi_swapchain = pSwap
    ctx.rtv = pRTV
    ctx.dcomp_device = dcomp_device
    ctx.dcomp_target = target
    ctx.dcomp_visual = visual


# ---- Primitive queueing API (to be flushed in end_scene) ----
def _norm_color(color: Tuple[int, int, int, int] | Tuple[int, int, int]) -> Tuple[int, int, int, int]:
    if len(color) == 4:
        return color  # RGBA 0-255
    r, g, b = color
    return (r, g, b, 255)


def queue_line(ctx: DXContext, x1: float, y1: float, x2: float, y2: float, color: Tuple[int, int, int] | Tuple[int, int, int, int]) -> None:
    if ctx and ctx.q_lines is not None:
        ctx.q_lines.append((x1, y1, x2, y2, _norm_color(color)))


def queue_rect(ctx: DXContext, x: float, y: float, w: float, h: float, color: Tuple[int, int, int] | Tuple[int, int, int, int], filled: bool = False) -> None:
    if ctx and ctx.q_rects is not None:
        ctx.q_rects.append((x, y, w, h, _norm_color(color), filled))


def queue_circle(ctx: DXContext, x: float, y: float, r: float, color: Tuple[int, int, int] | Tuple[int, int, int, int], filled: bool = False) -> None:
    if ctx and ctx.q_circles is not None:
        ctx.q_circles.append((x, y, r, _norm_color(color), filled))


def queue_text(ctx: DXContext, text: str, x: float, y: float, color: Tuple[int, int, int] | Tuple[int, int, int, int], size: int = 14, centered: bool = False) -> None:
    if ctx and ctx.q_texts is not None:
        ctx.q_texts.append((text, x, y, _norm_color(color), size, centered))


# ---- Pipeline setup and primitive flushing ----
def pipeline_ready(ctx: DXContext) -> bool:
    try:
        return bool(ctx) and bool(ctx.vs) and bool(ctx.ps) and bool(ctx.layout) and bool(ctx.rtv)
    except Exception:
        return False
def _compile_shader(src: bytes, entry: bytes, target: bytes) -> tuple[ctypes.c_void_p, int]:
    d3dc = ctypes.WinDLL('d3dcompiler_47.dll')
    D3DCompile = d3dc.D3DCompile
    D3DCompile.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p)]
    D3DCompile.restype = ctypes.c_long

    pCode = ctypes.c_void_p()
    pErr = ctypes.c_void_p()
    hr = D3DCompile(src, len(src), None, None, None, entry, target, 0, 0, ctypes.byref(pCode), ctypes.byref(pErr))
    if hr < 0 or not pCode.value:
        raise RuntimeError('Shader compile failed')
    blob = ctypes.cast(pCode, POINTER(ID3DBlob))
    ptr = blob.GetBufferPointer()
    size = blob.GetBufferSize()
    return (ctypes.c_void_p(ptr), int(size))


def _setup_pipeline(ctx: DXContext) -> None:
    dev = ctypes.cast(ctx.d3d_device, POINTER(ID3D11Device))
    # Minimal passthrough shaders: position (float2) and color (float4)
    vs_src = b"""
    struct VSIn { float2 pos : POSITION; float4 col : COLOR; };
    struct VSOut { float4 pos : SV_Position; float4 col : COLOR; };
    VSOut main(VSIn i) {
        VSOut o; o.pos = float4(i.pos, 0.0, 1.0); o.col = i.col; return o;
    }
    """
    ps_src = b"""
    struct PSIn { float4 pos : SV_Position; float4 col : COLOR; };
    float4 main(PSIn i) : SV_Target { return float4(i.col.rgb * i.col.a, i.col.a); }
    """
    vs_code, vs_size = _compile_shader(vs_src, b"main", b"vs_5_0")
    ps_code, ps_size = _compile_shader(ps_src, b"main", b"ps_5_0")
    pVS = ctypes.c_void_p()
    pPS = ctypes.c_void_p()
    if dev.CreateVertexShader(vs_code, vs_size, None, ctypes.byref(pVS)) < 0:
        return
    if dev.CreatePixelShader(ps_code, ps_size, None, ctypes.byref(pPS)) < 0:
        return
    ctx.vs = pVS
    ctx.ps = pPS

    # Input layout: POSITION(float2) at offset 0, COLOR(float4) at offset 8
    elems = (D3D11_INPUT_ELEMENT_DESC * 2)()
    elems[0] = D3D11_INPUT_ELEMENT_DESC(b"POSITION", 0, DXGI_FORMAT_R32G32_FLOAT, 0, 0, D3D11_INPUT_PER_VERTEX_DATA, 0)
    elems[1] = D3D11_INPUT_ELEMENT_DESC(b"COLOR", 0, DXGI_FORMAT_R32G32B32A32_FLOAT, 0, 8, D3D11_INPUT_PER_VERTEX_DATA, 0)
    pLayout = ctypes.c_void_p()
    if dev.CreateInputLayout(ctypes.byref(elems), 2, vs_code, vs_size, ctypes.byref(pLayout)) < 0:
        return
    ctx.layout = pLayout
    # Create premultiplied alpha blend state: Src=ONE, Dest=INV_SRC_ALPHA
    bd = D3D11_BLEND_DESC()
    bd.AlphaToCoverageEnable = 0
    bd.IndependentBlendEnable = 0
    rt = D3D11_RENDER_TARGET_BLEND_DESC()
    rt.BlendEnable = 1
    rt.SrcBlend = D3D11_BLEND_ONE
    rt.DestBlend = D3D11_BLEND_INV_SRC_ALPHA
    rt.BlendOp = D3D11_BLEND_OP_ADD
    rt.SrcBlendAlpha = D3D11_BLEND_ONE
    rt.DestBlendAlpha = D3D11_BLEND_INV_SRC_ALPHA
    rt.BlendOpAlpha = D3D11_BLEND_OP_ADD
    rt.RenderTargetWriteMask = D3D11_COLOR_WRITE_ENABLE_ALL
    bd.RenderTarget = (D3D11_RENDER_TARGET_BLEND_DESC * 8)(rt, *(D3D11_RENDER_TARGET_BLEND_DESC() for _ in range(7)))
    pBlend = ctypes.c_void_p()
    if dev.CreateBlendState(ctypes.byref(bd), ctypes.byref(pBlend)) >= 0:
        ctx.blend = pBlend


def _setup_text_pipeline(ctx: DXContext) -> None:
    dev = ctypes.cast(ctx.d3d_device, POINTER(ID3D11Device))
    # Textured vertex/pixel shaders: POSITION(float2), COLOR(float4), TEXCOORD(float2)
    vs_src = b"""
    struct VSIn { float2 pos : POSITION; float4 col : COLOR; float2 uv : TEXCOORD0; };
    struct VSOut { float4 pos : SV_Position; float4 col : COLOR; float2 uv : TEXCOORD0; };
    VSOut main(VSIn i) {
        VSOut o; o.pos = float4(i.pos, 0.0, 1.0); o.col = i.col; o.uv = i.uv; return o;
    }
    """
    ps_src = b"""
    Texture2D t0 : register(t0);
    SamplerState s0 : register(s0);
    struct PSIn { float4 pos : SV_Position; float4 col : COLOR; float2 uv : TEXCOORD0; };
    float4 main(PSIn i) : SV_Target {
        float4 tc = t0.Sample(s0, i.uv);
        float a = tc.a * i.col.a;
        return float4(tc.rgb * i.col.rgb * a, a);
    }
    """
    vs_code, vs_size = _compile_shader(vs_src, b"main", b"vs_5_0")
    ps_code, ps_size = _compile_shader(ps_src, b"main", b"ps_5_0")
    pVS = ctypes.c_void_p()
    pPS = ctypes.c_void_p()
    if dev.CreateVertexShader(vs_code, vs_size, None, ctypes.byref(pVS)) < 0:
        return
    if dev.CreatePixelShader(ps_code, ps_size, None, ctypes.byref(pPS)) < 0:
        return
    ctx.vs_text = pVS
    ctx.ps_text = pPS

    # Input layout: POS(0), COL(8), UV(24)
    elems = (D3D11_INPUT_ELEMENT_DESC * 3)()
    elems[0] = D3D11_INPUT_ELEMENT_DESC(b"POSITION", 0, DXGI_FORMAT_R32G32_FLOAT, 0, 0, D3D11_INPUT_PER_VERTEX_DATA, 0)
    elems[1] = D3D11_INPUT_ELEMENT_DESC(b"COLOR", 0, DXGI_FORMAT_R32G32B32A32_FLOAT, 0, 8, D3D11_INPUT_PER_VERTEX_DATA, 0)
    elems[2] = D3D11_INPUT_ELEMENT_DESC(b"TEXCOORD", 0, DXGI_FORMAT_R32G32_FLOAT, 0, 24, D3D11_INPUT_PER_VERTEX_DATA, 0)
    pLayout = ctypes.c_void_p()
    if dev.CreateInputLayout(ctypes.byref(elems), 3, vs_code, vs_size, ctypes.byref(pLayout)) < 0:
        return
    ctx.layout_text = pLayout

    # Sampler state (linear clamp)
    sd = D3D11_SAMPLER_DESC()
    sd.Filter = D3D11_FILTER_MIN_MAG_MIP_LINEAR
    sd.AddressU = D3D11_TEXTURE_ADDRESS_CLAMP
    sd.AddressV = D3D11_TEXTURE_ADDRESS_CLAMP
    sd.AddressW = D3D11_TEXTURE_ADDRESS_CLAMP
    sd.MipLODBias = 0.0
    sd.MaxAnisotropy = 1
    sd.ComparisonFunc = D3D11_COMPARISON_ALWAYS
    sd.BorderColor = (ctypes.c_float * 4)(0,0,0,0)
    sd.MinLOD = 0.0
    sd.MaxLOD = 0.0
    pSamp = ctypes.c_void_p()
    if dev.CreateSamplerState(ctypes.byref(sd), ctypes.byref(pSamp)) >= 0:
        ctx.sampler = pSamp


def _ensure_font_atlas(ctx: DXContext, font_path: Optional[str], size_px: int) -> None:
    if ctx.font_srv and ctx.glyphs and ctx._atlas_w and ctx._atlas_h and ctx.font_size_px == size_px:
        return
    # Build atlas with Pillow
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return
    chars = [chr(i) for i in range(32, 127)]
    # Load font
    try:
        font = ImageFont.truetype(font_path or "arial.ttf", size_px)
    except Exception:
        font = ImageFont.load_default()
    # Measure
    pad = 2
    max_w = max(font.getlength(c) if hasattr(font, 'getlength') else font.getsize(c)[0] for c in chars)
    max_h = max(font.getbbox(c)[3] - font.getbbox(c)[1] if hasattr(font, 'getbbox') else font.getsize(c)[1] for c in chars)
    cols = 16
    rows = (len(chars) + cols - 1) // cols
    cell_w = int(max_w + pad)
    cell_h = int(max_h + pad)
    atlas_w = cols * cell_w
    atlas_h = rows * cell_h
    img = Image.new("RGBA", (atlas_w, atlas_h), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    glyphs: Dict[str, Tuple[float,float,float,float,int,int,int]] = {}
    for idx, ch in enumerate(chars):
        cx = (idx % cols) * cell_w
        cy = (idx // cols) * cell_h
        # Use textbbox to get offset and baseline info if available
        try:
            bbox = draw.textbbox((0,0), ch, font=font)
            gw, gh = bbox[2]-bbox[0], bbox[3]-bbox[1]
            ox, oy = 0, 0
        except Exception:
            gw, gh = font.getsize(ch)
            ox, oy = 0, 0
        draw.text((cx, cy), ch, font=font, fill=(255,255,255,255))
        u0 = cx / atlas_w; v0 = cy / atlas_h
        u1 = (cx + max(1, gw)) / atlas_w; v1 = (cy + max(1, gh)) / atlas_h
        adv = int(font.getlength(ch)) if hasattr(font, 'getlength') else gw
        glyphs[ch] = (u0, v0, u1, v1, ox, oy, adv)

    # Upload to GPU
    data = img.tobytes("raw", "RGBA")
    dev = ctypes.cast(ctx.d3d_device, POINTER(ID3D11Device))
    desc = D3D11_TEXTURE2D_DESC()
    desc.Width = atlas_w
    desc.Height = atlas_h
    desc.MipLevels = 1
    desc.ArraySize = 1
    desc.Format = DXGI_FORMAT_R8G8B8A8_UNORM
    desc.SampleDesc = (ctypes.c_uint * 2)(1, 0)
    desc.Usage = D3D11_USAGE_IMMUTABLE
    desc.BindFlags = D3D11_BIND_SHADER_RESOURCE
    desc.CPUAccessFlags = 0
    desc.MiscFlags = 0
    srd = D3D11_SUBRESOURCE_DATA()
    buf = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    srd.pSysMem = ctypes.cast(buf, ctypes.c_void_p)
    srd.SysMemPitch = atlas_w * 4
    srd.SysMemSlicePitch = len(data)
    pTex = ctypes.c_void_p()
    if dev.CreateTexture2D(ctypes.byref(desc), ctypes.byref(srd), ctypes.byref(pTex)) < 0:
        return
    pSRV = ctypes.c_void_p()
    if dev.CreateShaderResourceView(pTex, None, ctypes.byref(pSRV)) < 0:
        return
    ctx.font_tex = pTex
    ctx.font_srv = pSRV
    ctx.glyphs = glyphs
    ctx._atlas_w = atlas_w
    ctx._atlas_h = atlas_h
    ctx.font_size_px = size_px
def _flush_primitives(ctx: DXContext) -> None:
    # If pipeline is not ready, do nothing (GDI still draws).
    if not (ctx.vs and ctx.ps and ctx.layout):
        return
    dev = ctypes.cast(ctx.d3d_device, POINTER(ID3D11Device))
    devctx = ctypes.cast(ctx.d3d_context, POINTER(ID3D11DeviceContext))

    # Build vertex buffer from queued primitives, expanding to triangles
    verts: List[float] = []

    def rgba_to_f(color: Tuple[int, int, int, int]) -> tuple[float, float, float, float]:
        r, g, b, a = color
        return (r/255.0, g/255.0, b/255.0, a/255.0)

    def to_ndc(x: float, y: float) -> tuple[float, float]:
        nx = (x / max(1, ctx.width)) * 2.0 - 1.0
        ny = 1.0 - (y / max(1, ctx.height)) * 2.0
        return nx, ny

    # Helpers
    px_ndc_x = 2.0 / max(1, ctx.width)
    px_ndc_y = 2.0 / max(1, ctx.height)

    def add_tri(ax, ay, bx, by, cx, cy, c):
        verts.extend([ax, ay, *c,  bx, by, *c,  cx, cy, *c])

    def add_quad(ax, ay, bx, by, cx, cy, dx, dy, c):
        # two triangles: a-b-c and a-c-d
        add_tri(ax, ay, bx, by, cx, cy, c)
        add_tri(ax, ay, cx, cy, dx, dy, c)

    def add_line_quad(x1, y1, x2, y2, c, thickness_px=1.0):
        # Build a screen-space perpendicular of half-thickness
        # Convert to NDC first
        X1, Y1 = to_ndc(x1, y1)
        X2, Y2 = to_ndc(x2, y2)
        dx = X2 - X1
        dy = Y2 - Y1
        length = (dx*dx + dy*dy) ** 0.5
        if length == 0:
            # Degenerate: draw a small quad centered at the point
            hx = px_ndc_x * thickness_px * 0.5
            hy = px_ndc_y * thickness_px * 0.5
            add_quad(X1 - hx, Y1 - hy, X1 + hx, Y1 - hy, X1 + hx, Y1 + hy, X1 - hx, Y1 + hy, c)
            return
        # Perpendicular normalized
        nx = -dy / length
        ny = dx / length
        # Scale by half thickness in NDC: approximate isotropic by averaging pixel scales
        sx = nx * px_ndc_x * thickness_px * 0.5 * (ctx.height/ctx.width)
        sy = ny * px_ndc_y * thickness_px * 0.5
        # Four corners
        ax, ay = X1 - sx, Y1 - sy
        bx, by = X1 + sx, Y1 + sy
        cx, cy = X2 + sx, Y2 + sy
        dx_, dy_ = X2 - sx, Y2 - sy
        add_quad(ax, ay, bx, by, cx, cy, dx_, dy_, c)

    # Filled rects as 2 triangles
    for (x, y, w, h, col, filled) in ctx.q_rects:
        if not filled:
            # Outline rect using 4 line quads of 1px thickness
            c = rgba_to_f(col)
            add_line_quad(x, y, x + w, y, c)
            add_line_quad(x + w, y, x + w, y + h, c)
            add_line_quad(x + w, y + h, x, y + h, c)
            add_line_quad(x, y + h, x, y, c)
        else:
            c = rgba_to_f(col)
            x0, y0 = to_ndc(x, y)
            x1, y1 = to_ndc(x + w, y + h)
            # tri 1: (x0,y0),(x1,y0),(x0,y1); tri 2: (x0,y1),(x1,y0),(x1,y1)
            add_tri(x0, y0, x1, y0, x0, y1, c)
            add_tri(x0, y1, x1, y0, x1, y1, c)

    # Lines: expand to quads of 1px thickness
    for (x1, y1, x2, y2, col) in ctx.q_lines:
        c = rgba_to_f(col)
        add_line_quad(x1, y1, x2, y2, c)

    # Circles
    SEG = 32
    for (cx, cy, r, col, filled) in ctx.q_circles:
        c = rgba_to_f(col)
        if filled:
            # triangle fan around center
            cx_ndc, cy_ndc = to_ndc(cx, cy)
            import math
            prev = None
            for i in range(SEG + 1):
                ang = (i / SEG) * math.tau
                x = cx + r * math.cos(ang)
                y = cy + r * math.sin(ang)
                X, Y = to_ndc(x, y)
                if prev is not None:
                    add_tri(cx_ndc, cy_ndc, prev[0], prev[1], X, Y, c)
                prev = (X, Y)
        else:
            # outline as polyline with line quads
            import math
            pts = []
            for i in range(SEG):
                ang = (i / SEG) * math.tau
                x = cx + r * math.cos(ang)
                y = cy + r * math.sin(ang)
                pts.append((x, y))
            for i in range(SEG):
                x1, y1 = pts[i]
                x2, y2 = pts[(i + 1) % SEG]
                add_line_quad(x1, y1, x2, y2, c)

    if not verts:
        return
    data = (ctypes.c_float * len(verts))(*verts)

    stride = ctypes.c_uint(24)  # 6 floats * 4 bytes
    offset = ctypes.c_uint(0)

    # Create/resize dynamic vertex buffer if needed
    needed_bytes = len(verts) * 4
    if ctx.vbuf is None or ctx.vbuf_capacity < needed_bytes:
        # D3D11_BUFFER_DESC
        class BUFFER_DESC(ctypes.Structure):
            _fields_ = [
                ("ByteWidth", ctypes.c_uint),
                ("Usage", ctypes.c_uint),
                ("BindFlags", ctypes.c_uint),
                ("CPUAccessFlags", ctypes.c_uint),
                ("MiscFlags", ctypes.c_uint),
                ("StructureByteStride", ctypes.c_uint),
            ]
        D3D11_USAGE_DYNAMIC = 2
        D3D11_BIND_VERTEX_BUFFER = 0x1
        D3D11_CPU_ACCESS_WRITE = 0x10000
        bd = BUFFER_DESC()
        bd.ByteWidth = max(needed_bytes, 4096)
        bd.Usage = D3D11_USAGE_DYNAMIC
        bd.BindFlags = D3D11_BIND_VERTEX_BUFFER
        bd.CPUAccessFlags = D3D11_CPU_ACCESS_WRITE
        bd.MiscFlags = 0
        bd.StructureByteStride = 0
        pb = ctypes.c_void_p()
        hrb = dev.CreateBuffer(ctypes.byref(bd), None, ctypes.byref(pb))
        if hrb < 0 or not pb:
            return
        ctx.vbuf = pb
        ctx.vbuf_capacity = bd.ByteWidth

    # Update buffer via Map/Unmap (not exposed; for brevity, recreate each time if small)
    # Simpler path: recreate immutable buffer each frame (less efficient but simpler)
    class SUBRESOURCE_DATA(ctypes.Structure):
        _fields_ = [("pSysMem", ctypes.c_void_p), ("SysMemPitch", ctypes.c_uint), ("SysMemSlicePitch", ctypes.c_uint)]
    class BUFFER_DESC2(ctypes.Structure):
        _fields_ = [
            ("ByteWidth", ctypes.c_uint),
            ("Usage", ctypes.c_uint),
            ("BindFlags", ctypes.c_uint),
            ("CPUAccessFlags", ctypes.c_uint),
            ("MiscFlags", ctypes.c_uint),
            ("StructureByteStride", ctypes.c_uint),
        ]
    D3D11_USAGE_IMMUTABLE = 0
    D3D11_BIND_VERTEX_BUFFER = 0x1
    bd2 = BUFFER_DESC2()
    bd2.ByteWidth = needed_bytes
    bd2.Usage = D3D11_USAGE_IMMUTABLE
    bd2.BindFlags = D3D11_BIND_VERTEX_BUFFER
    bd2.CPUAccessFlags = 0
    bd2.MiscFlags = 0
    bd2.StructureByteStride = 0
    init = SUBRESOURCE_DATA(ctypes.cast(data, ctypes.c_void_p), 0, 0)
    vb = ctypes.c_void_p()
    if dev.CreateBuffer(ctypes.byref(bd2), ctypes.byref(init), ctypes.byref(vb)) < 0:
        return

    # IA setup
    devctx.IASetInputLayout(ctx.layout)
    # Topology: TRIANGLELIST for rects; but since we mix, use TRIANGLELIST and Draw lines separately? For simplicity, draw all as triangles and skip lines when mixed.
    # Here we just bind and draw the entire buffer as TRIANGLELIST; lines appended will look wrong but GDI still draws correct visuals.
    D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST = 4
    devctx.IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST)
    bufs = (ctypes.c_void_p * 1)(vb)
    strides = (ctypes.c_uint * 1)(stride.value)
    offsets = (ctypes.c_uint * 1)(offset.value)
    devctx.IASetVertexBuffers(0, 1, bufs, strides, offsets)

    # Shaders & blend (if available)
    if ctx.vs:
        devctx.VSSetShader(ctx.vs, None, 0)
    if ctx.ps:
        devctx.PSSetShader(ctx.ps, None, 0)
    if ctx.blend:
        blend_factor = (ctypes.c_float * 4)(0.0, 0.0, 0.0, 0.0)
        devctx.OMSetBlendState(ctx.blend, blend_factor, 0xFFFFFFFF)

    # Draw
    vertex_count = len(verts) // 6
    devctx.Draw(vertex_count, 0)

    # --- Text rendering ---
    if ctx.vs_text and ctx.ps_text and ctx.layout_text and ctx.font_srv and ctx.sampler and ctx.q_texts:
        tv: List[float] = []  # x,y, r,g,b,a, u,v
        # Build text quads
        for (text, x, y, col, size, centered) in ctx.q_texts:
            scale = max(1e-6, size / max(1, ctx.font_size_px))
            # Simple baseline; centered horizontally if requested
            import math
            total_w = 0
            if centered:
                for ch in text:
                    g = ctx.glyphs.get(ch)
                    if g:
                        total_w += int(g[6] * scale)
            pen_x = x - total_w * 0.5 if centered else x
            pen_y = y
            for ch in text:
                g = ctx.glyphs.get(ch)
                if not g:
                    continue
                u0,v0,u1,v1,ox,oy,adv = g
                gw = int((u1 - u0) * ctx._atlas_w)
                gh = int((v1 - v0) * ctx._atlas_h)
                px = pen_x + ox * scale
                py = pen_y + oy * scale
                x0,y0 = to_ndc(px, py)
                x1,y1 = to_ndc(px + gw * scale, py + gh * scale)
                r,gc,bc,ac = rgba_to_f(col)
                # Quad with texcoords
                # tri A
                tv.extend([x0,y0,r,gc,bc,ac, u0,v0])
                tv.extend([x1,y0,r,gc,bc,ac, u1,v0])
                tv.extend([x0,y1,r,gc,bc,ac, u0,v1])
                # tri B
                tv.extend([x0,y1,r,gc,bc,ac, u0,v1])
                tv.extend([x1,y0,r,gc,bc,ac, u1,v0])
                tv.extend([x1,y1,r,gc,bc,ac, u1,v1])
                pen_x += adv * scale
        if tv:
            data2 = (ctypes.c_float * len(tv))(*tv)
            stride2 = ctypes.c_uint(32)  # 8 floats per-vertex
            offset2 = ctypes.c_uint(0)
            # Create transient immutable buffer for text verts
            class SRD(ctypes.Structure):
                _fields_ = [("pSysMem", ctypes.c_void_p), ("SysMemPitch", ctypes.c_uint), ("SysMemSlicePitch", ctypes.c_uint)]
            class BD(ctypes.Structure):
                _fields_ = [("ByteWidth", ctypes.c_uint),("Usage", ctypes.c_uint),("BindFlags", ctypes.c_uint),("CPUAccessFlags", ctypes.c_uint),("MiscFlags", ctypes.c_uint),("StructureByteStride", ctypes.c_uint)]
            D3D11_USAGE_IMMUTABLE = 0
            D3D11_BIND_VERTEX_BUFFER = 0x1
            bd = BD(); bd.ByteWidth = len(tv)*4; bd.Usage=D3D11_USAGE_IMMUTABLE; bd.BindFlags=D3D11_BIND_VERTEX_BUFFER; bd.CPUAccessFlags=0; bd.MiscFlags=0; bd.StructureByteStride=0
            init = SRD(ctypes.cast(data2, ctypes.c_void_p), 0, 0)
            vb2 = ctypes.c_void_p()
            if dev.CreateBuffer(ctypes.byref(bd), ctypes.byref(init), ctypes.byref(vb2)) >= 0:
                # Bind text pipeline
                devctx.IASetInputLayout(ctx.layout_text)
                D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST = 4
                devctx.IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST)
                bufs2 = (ctypes.c_void_p * 1)(vb2)
                strides2 = (ctypes.c_uint * 1)(stride2.value)
                offsets2 = (ctypes.c_uint * 1)(offset2.value)
                devctx.IASetVertexBuffers(0, 1, bufs2, strides2, offsets2)
                # Shaders
                devctx.VSSetShader(ctx.vs_text, None, 0)
                devctx.PSSetShader(ctx.ps_text, None, 0)
                # Resources
                srvs = (ctypes.c_void_p * 1)(ctx.font_srv)
                samps = (ctypes.c_void_p * 1)(ctx.sampler)
                devctx.PSSetShaderResources(0, 1, srvs)
                devctx.PSSetSamplers(0, 1, samps)
                # Blend
                if ctx.blend:
                    blend_factor = (ctypes.c_float * 4)(0.0, 0.0, 0.0, 0.0)
                    devctx.OMSetBlendState(ctx.blend, blend_factor, 0xFFFFFFFF)
                # Draw
                devctx.Draw(len(tv)//8, 0)