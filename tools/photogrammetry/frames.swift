// Pull evenly spaced frames out of a clip, to judge a capture before
// spending twenty minutes reconstructing it.
import Foundation
import AVFoundation
import CoreImage

let a = CommandLine.arguments
guard a.count >= 3 else { print("usage: frames <video> <outdir> [count]"); exit(1) }
let count = a.count > 3 ? (Int(a[3]) ?? 9) : 9
let outDir = URL(fileURLWithPath: (a[2] as NSString).expandingTildeInPath)
try? FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)

let asset = AVURLAsset(url: URL(fileURLWithPath: (a[1] as NSString).expandingTildeInPath))
let dur = try await asset.load(.duration)
let secs = CMTimeGetSeconds(dur)
let tracks = try await asset.loadTracks(withMediaType: .video)
if let t = tracks.first {
    let size = try await t.load(.naturalSize)
    let fps = try await t.load(.nominalFrameRate)
    print(String(format: "clip: %.1fs  %.0fx%.0f  %.0f fps", secs, size.width, size.height, fps))
}

let gen = AVAssetImageGenerator(asset: asset)
gen.appliesPreferredTrackTransform = true
gen.requestedTimeToleranceBefore = .zero
gen.requestedTimeToleranceAfter = .zero
gen.maximumSize = CGSize(width: 1100, height: 1100)
let ctx = CIContext()
for i in 0..<count {
    let t = CMTime(seconds: secs * Double(i) / Double(count - 1 == 0 ? 1 : count - 1) * 0.98,
                   preferredTimescale: 600)
    if let (cg, _) = try? await gen.image(at: t) {
        let url = outDir.appendingPathComponent(String(format: "f%02d.jpg", i))
        try? ctx.writeJPEGRepresentation(of: CIImage(cgImage: cg), to: url,
            colorSpace: CGColorSpaceCreateDeviceRGB(),
            options: [kCGImageDestinationLossyCompressionQuality as CIImageRepresentationOption: 0.9])
        print(String(format: "  %.1fs -> %@", CMTimeGetSeconds(t), url.lastPathComponent))
    }
}
