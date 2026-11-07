// Fixed-rate video frame extractor for macOS (AVFoundation; no ffmpeg needed).
// usage: extract_frames <video> <outdir> <prefix> [fps=1] [max_px=1280] [quality=0.8]
// Writes <outdir>/<prefix>_t<seconds>.jpg for t = 0, 1/fps, 2/fps ... (< duration), upright (track transform applied),
// long side at most max_px (0 = full resolution). Prints one JSON line per frame: {"t": 12.000, "file": "...", "w": .., "h": ..}
// and first a header line {"duration": .., "width": .., "height": .., "fps_nominal": ..}. Existing files are kept (resumable).
import Foundation
import AVFoundation
import CoreImage

let a = CommandLine.arguments
guard a.count >= 4 else {
    print("usage: extract_frames <video> <outdir> <prefix> [fps=1] [max_px=1280] [quality=0.8]"); exit(1)
}
let fps = a.count > 4 ? (Double(a[4]) ?? 1.0) : 1.0
let maxPx = a.count > 5 ? (Double(a[5]) ?? 1280) : 1280
let quality = a.count > 6 ? (Double(a[6]) ?? 0.8) : 0.8
let outDir = URL(fileURLWithPath: (a[2] as NSString).expandingTildeInPath)
try? FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)
let asset = AVURLAsset(url: URL(fileURLWithPath: (a[1] as NSString).expandingTildeInPath))
let dur = CMTimeGetSeconds(try await asset.load(.duration))
var w = 0.0, h = 0.0, nominal = 0.0
if let t = try await asset.loadTracks(withMediaType: .video).first {
    let size = try await t.load(.naturalSize)
    let tr = try await t.load(.preferredTransform)
    let r = CGRect(origin: .zero, size: size).applying(tr)
    w = abs(Double(r.width)); h = abs(Double(r.height)); nominal = Double(try await t.load(.nominalFrameRate))
}
print(String(format: "{\"duration\": %.4f, \"width\": %.0f, \"height\": %.0f, \"fps_nominal\": %.3f}", dur, w, h, nominal))
let gen = AVAssetImageGenerator(asset: asset)
gen.appliesPreferredTrackTransform = true
gen.requestedTimeToleranceBefore = .zero
gen.requestedTimeToleranceAfter = .zero
if maxPx > 0 { gen.maximumSize = CGSize(width: maxPx, height: maxPx) }
let ctx = CIContext()
var i = 0
while true {
    let ts = Double(i) / fps
    if ts >= dur - 0.02 { break }
    let name = String(format: "%@_t%07.2f.jpg", a[3], ts)
    let url = outDir.appendingPathComponent(name)
    if !FileManager.default.fileExists(atPath: url.path) {
        if let (cg, _) = try? await gen.image(at: CMTime(seconds: ts, preferredTimescale: 600)) {
            try? ctx.writeJPEGRepresentation(of: CIImage(cgImage: cg), to: url, colorSpace: CGColorSpaceCreateDeviceRGB(),
                options: [kCGImageDestinationLossyCompressionQuality as CIImageRepresentationOption: quality])
            print(String(format: "{\"t\": %.3f, \"file\": \"%@\", \"w\": %d, \"h\": %d}", ts, name, cg.width, cg.height))
        } else {
            print(String(format: "{\"t\": %.3f, \"error\": \"no frame\"}", ts))
        }
    } else {
        print(String(format: "{\"t\": %.3f, \"file\": \"%@\", \"existing\": true}", ts, name))
    }
    i += 1
}
