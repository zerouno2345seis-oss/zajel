// pbvision: يصنّف الصور بإطار Vision المدمج في macOS (بلا إنترنت).
// الاستعمال: pbvision ملف1 ملف2 …  ← سطر JSON لكل ملف: {"path", "labels": {"معرّف": ثقة}, "faces": عدد, "screenshot": bool}
import Foundation
import Vision
import ImageIO

func analyze(_ path: String) -> [String: Any] {
    var out: [String: Any] = ["path": path, "labels": [String: Double](), "faces": 0, "screenshot": false]
    let url = URL(fileURLWithPath: path)
    guard let src = CGImageSourceCreateWithURL(url as CFURL, nil),
          let img = CGImageSourceCreateThumbnailAtIndex(src, 0, [kCGImageSourceCreateThumbnailFromImageAlways: true,
                                                                  kCGImageSourceThumbnailMaxPixelSize: 1024,
                                                                  kCGImageSourceCreateThumbnailWithTransform: true] as CFDictionary)
    else { out["error"] = "unreadable"; return out }
    if let props = CGImageSourceCopyPropertiesAtIndex(src, 0, nil) as? [String: Any],
       let exif = props[kCGImagePropertyExifDictionary as String] as? [String: Any],
       let c = exif[kCGImagePropertyExifUserComment as String] as? String, c.lowercased().contains("screenshot") {
        out["screenshot"] = true
    }
    let cls = VNClassifyImageRequest()
    let faces = VNDetectFaceRectanglesRequest()
    let h = VNImageRequestHandler(cgImage: img, options: [:])
    try? h.perform([cls, faces])
    var labels = [String: Double]()
    for o in cls.results ?? [] where o.confidence > 0.3 { labels[o.identifier] = Double(o.confidence) }
    out["labels"] = labels
    out["faces"] = faces.results?.count ?? 0
    return out
}

for p in CommandLine.arguments.dropFirst() {
    if let d = try? JSONSerialization.data(withJSONObject: analyze(p)), let s = String(data: d, encoding: .utf8) {
        print(s)
        fflush(stdout)
    }
}
