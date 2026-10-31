// Local photogrammetry on this Mac, using Apple's own engine.
//
// Nothing to install: PhotogrammetrySession ships with macOS and runs on
// the Apple Silicon GPU. That matters for the service — a client's home
// video never has to leave the machine.
//
// Build:  swiftc -O -o scan main.swift
// Use:    ./scan <video.mov | image-folder> <output.usdz> [detail] [frames]
//
// Object Capture is built for outside-in capture: walking around a thing
// and pointing inward. A garden studio or a house exterior suits it. A
// room photographed from the inside is the opposite case and will do
// noticeably worse — use Gaussian splatting for interiors.

import Foundation
import RealityKit
import AVFoundation
import CoreImage

let args = CommandLine.arguments
guard args.count >= 3 else {
    print("""
    usage: scan <video.mov | image-folder> <output.usdz> [detail] [frames]
      detail  preview | reduced | medium | full | raw     (default: medium)
      frames  how many frames to pull from a video        (default: 160)
    """)
    exit(1)
}

let inputPath = (args[1] as NSString).expandingTildeInPath
let outputPath = (args[2] as NSString).expandingTildeInPath
let detailArg = args.count > 3 ? args[3].lowercased() : "medium"
let frameTarget = args.count > 4 ? (Int(args[4]) ?? 160) : 160

let detail: PhotogrammetrySession.Request.Detail = {
    switch detailArg {
    case "preview": return .preview
    case "reduced": return .reduced
    case "full":    return .full
    case "raw":     return .raw
    default:        return .medium
    }
}()

let fm = FileManager.default
var isDir: ObjCBool = false
guard fm.fileExists(atPath: inputPath, isDirectory: &isDir) else {
    print("error: no such file or folder: \(inputPath)")
    exit(1)
}

// ---------------------------------------------------------------- frames
// A video has to become stills. Even spacing across the whole clip keeps
// the overlap consistent, which is what the solver actually cares about.
func extractFrames(from videoPath: String, count: Int) async throws -> URL {
    let asset = AVURLAsset(url: URL(fileURLWithPath: videoPath))
    let duration = try await asset.load(.duration)
    let seconds = CMTimeGetSeconds(duration)
    guard seconds > 0 else { throw NSError(domain: "scan", code: 2,
        userInfo: [NSLocalizedDescriptionKey: "video has no duration"]) }

    let dir = URL(fileURLWithPath: NSTemporaryDirectory())
        .appendingPathComponent("scan-frames-\(UUID().uuidString)")
    try fm.createDirectory(at: dir, withIntermediateDirectories: true)

    let gen = AVAssetImageGenerator(asset: asset)
    gen.appliesPreferredTrackTransform = true
    gen.requestedTimeToleranceBefore = .zero
    gen.requestedTimeToleranceAfter = .zero
    gen.maximumSize = CGSize(width: 2560, height: 2560)

    let times: [CMTime] = (0..<count).map {
        CMTime(seconds: seconds * Double($0) / Double(count), preferredTimescale: 600)
    }

    let ctx = CIContext()
    var written = 0
    for (i, t) in times.enumerated() {
        do {
            let (cg, _) = try await gen.image(at: t)
            let ci = CIImage(cgImage: cg)
            let url = dir.appendingPathComponent(String(format: "frame_%04d.jpg", i))
            try ctx.writeJPEGRepresentation(of: ci, to: url,
                                            colorSpace: CGColorSpaceCreateDeviceRGB(),
                                            options: [kCGImageDestinationLossyCompressionQuality as CIImageRepresentationOption: 0.92])
            written += 1
            if written % 20 == 0 {
                print("  extracted \(written)/\(count) frames")
                fflush(stdout)
            }
        } catch {
            // a frame that will not decode is not worth stopping for
        }
    }
    print("extracted \(written) frames from \(String(format: "%.1f", seconds))s of video")
    return dir
}

// ---------------------------------------------------------------- run
func run() async {
    var imageFolder: URL
    var temporary: URL? = nil

    if isDir.boolValue {
        imageFolder = URL(fileURLWithPath: inputPath)
        let n = (try? fm.contentsOfDirectory(atPath: inputPath))?.filter {
            ["jpg", "jpeg", "png", "heic", "tif", "tiff"].contains(($0 as NSString).pathExtension.lowercased())
        }.count ?? 0
        print("input: folder with \(n) images")
    } else {
        print("input: video, extracting frames…")
        do {
            let dir = try await extractFrames(from: inputPath, count: frameTarget)
            imageFolder = dir
            temporary = dir
        } catch {
            print("error extracting frames: \(error.localizedDescription)")
            exit(1)
        }
    }

    var config = PhotogrammetrySession.Configuration()
    config.featureSensitivity = .high
    config.sampleOrdering = .sequential     // frames came off a walk, in order
    config.isObjectMaskingEnabled = false   // a building is not an object on a turntable

    let session: PhotogrammetrySession
    do {
        session = try PhotogrammetrySession(input: imageFolder, configuration: config)
    } catch {
        print("error: could not start a photogrammetry session: \(error.localizedDescription)")
        exit(1)
    }

    let out = URL(fileURLWithPath: outputPath)
    let request = PhotogrammetrySession.Request.modelFile(url: out, detail: detail)

    let started = Date()
    do {
        try session.process(requests: [request])
    } catch {
        print("error: \(error.localizedDescription)")
        exit(1)
    }

    var lastPrinted = -1
    do {
    for try await output in session.outputs {
        switch output {
        case .requestProgress(_, let fraction):
            let pct = Int(fraction * 100)
            if pct / 5 != lastPrinted / 5 {
                lastPrinted = pct
                let mins = Date().timeIntervalSince(started) / 60
                print(String(format: "  %3d%%   %.1f min elapsed", pct, mins))
                fflush(stdout)
            }
        case .requestComplete(_, _):
            let mins = Date().timeIntervalSince(started) / 60
            print(String(format: "done in %.1f min -> %@", mins, outputPath))
        case .requestError(_, let error):
            print("failed: \(error.localizedDescription)")
        case .processingComplete:
            if let t = temporary { try? fm.removeItem(at: t) }
            exit(0)
        case .invalidSample(let id, let reason):
            print("  skipped sample \(id): \(reason)")
        case .processingCancelled:
            print("cancelled")
            exit(1)
        default:
            break
        }
    }
    } catch {
        print("stream error: \(error.localizedDescription)")
        exit(1)
    }
}

await run()
