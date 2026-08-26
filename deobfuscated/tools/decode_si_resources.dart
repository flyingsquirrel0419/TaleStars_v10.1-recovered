import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:jovial_svg/src/affine.dart';
import 'package:jovial_svg/src/common_noui.dart';
import 'package:jovial_svg/src/compact_noui.dart';
import 'package:jovial_svg/src/path_noui.dart';

class Reader {
  final Uint8List bytes;
  int offset = 0;
  Reader(this.bytes);

  int u8() => bytes[offset++];
  int u16() {
    final value = (bytes[offset] << 8) | bytes[offset + 1];
    offset += 2;
    return value;
  }

  int u32() {
    final value = (bytes[offset] << 24) |
        (bytes[offset + 1] << 16) |
        (bytes[offset + 2] << 8) |
        bytes[offset + 3];
    offset += 4;
    return value;
  }

  double f32() {
    final value = ByteData.sublistView(bytes, offset, offset + 4).getFloat32(0, Endian.big);
    offset += 4;
    return value;
  }

  double f32Little() {
    final value = ByteData.sublistView(bytes, offset, offset + 4).getFloat32(0, Endian.little);
    offset += 4;
    return value;
  }

  double f64() {
    final value = ByteData.sublistView(bytes, offset, offset + 8).getFloat64(0, Endian.big);
    offset += 8;
    return value;
  }

  double f64Little() {
    final value = ByteData.sublistView(bytes, offset, offset + 8).getFloat64(0, Endian.little);
    offset += 8;
    return value;
  }

  int small() {
    final value = u8();
    if (value < 0xfe) return value;
    if (value == 0xfe) return u16();
    return u32();
  }

  Uint8List take(int length) {
    final value = Uint8List.fromList(bytes.sublist(offset, offset + length));
    offset += length;
    return value;
  }
}

class ParsedSI {
  final int version;
  final bool bigFloats;
  final double? width;
  final double? height;
  final List<String> strings;
  final List<List<String>> stringLists;
  final List<List<double>> floatLists;
  final List<double> floatValues;
  final List<SIImageData> images;
  final List<double> args;
  final List<double> transforms;
  final Uint8List children;
  final int numPaths;
  final int numPaints;

  ParsedSI({
    required this.version,
    required this.bigFloats,
    required this.width,
    required this.height,
    required this.strings,
    required this.stringLists,
    required this.floatLists,
    required this.floatValues,
    required this.images,
    required this.args,
    required this.transforms,
    required this.children,
    required this.numPaths,
    required this.numPaints,
  });
}

ParsedSI parseSI(Uint8List bytes) {
  final r = Reader(bytes);
  if (r.u32() != 0xb0b01e07) throw FormatException('bad SI magic');
  r.u8();
  final version = r.u16();
  if (version < 1 || version > 12) throw FormatException('unsupported SI version $version');
  final flags = r.u8();
  final hasWidth = flags & 1 != 0;
  final hasHeight = flags & 2 != 0;
  final bigFloats = flags & 4 != 0;
  final hasTint = flags & 8 != 0;
  final hasCurrentColor = version > 8 && flags & 16 != 0;
  final hasViewport = version > 8 && flags & 32 != 0;
  final numPaths = r.u32();
  final numPaints = r.u32();
  final argsLength = r.u32();
  final transformsLength = r.u32();
  double readFloat() => bigFloats ? r.f64() : r.f32();
  double readLittleFloat() => bigFloats ? r.f64Little() : r.f32Little();
  final args = List<double>.generate(argsLength, (_) => readLittleFloat());
  final transforms = List<double>.generate(transformsLength, (_) => readLittleFloat());
  final width = hasWidth ? readFloat() : null;
  final height = hasHeight ? readFloat() : null;
  if (hasTint) {
    r.u32();
    r.u8();
  }
  if (hasCurrentColor) r.u32();
  if (hasViewport) {
    readFloat();
    readFloat();
    readFloat();
    readFloat();
  }
  final strings = List<String>.generate(
    r.small(),
    (_) => utf8.decode(r.take(r.small()), allowMalformed: true),
  );
  final stringLists = version <= 9
      ? <List<String>>[]
      : List<List<String>>.generate(
          r.small(),
          (_) => List<String>.generate(r.small(), (_) => strings[r.small()]),
        );
  final floatLists = List<List<double>>.generate(
    r.small(),
    (_) => List<double>.generate(r.small(), (_) => readFloat()),
  );
  final floatValues = version < 7 ? <double>[] : List<double>.generate(r.small(), (_) => readFloat());
  final images = List<SIImageData>.generate(r.small(), (_) {
    final x = readFloat();
    final y = readFloat();
    final width = readFloat();
    final height = readFloat();
    return SIImageData(x: x, y: y, width: width, height: height, encoded: r.take(r.small()));
  });
  return ParsedSI(
    version: version,
    bigFloats: bigFloats,
    width: width,
    height: height,
    strings: strings,
    stringLists: stringLists,
    floatLists: floatLists,
    floatValues: floatValues,
    images: images,
    args: args,
    transforms: transforms,
    children: Uint8List.fromList(bytes.sublist(r.offset)),
    numPaths: numPaths,
    numPaints: numPaints,
  );
}

String esc(Object? value) => const HtmlEscape(HtmlEscapeMode.element).convert('$value');
String num(double value) => value.toStringAsFixed(6).replaceFirst(RegExp(r'0+$'), '').replaceFirst(RegExp(r'\.$'), '');

class SvgPathBuilder extends StringPathBuilder implements EnhancedPathBuilder {
  @override
  void addOval(RectT rect) {
    final cx = rect.left + rect.width / 2;
    final cy = rect.top + rect.height / 2;
    moveTo(PointT(cx + rect.width / 2, cy));
    arcToPoint(PointT(cx - rect.width / 2, cy), radius: RadiusT(rect.width / 2, rect.height / 2), rotation: 0, largeArc: true, clockwise: true);
    arcToPoint(PointT(cx + rect.width / 2, cy), radius: RadiusT(rect.width / 2, rect.height / 2), rotation: 0, largeArc: true, clockwise: true);
    close();
  }
}

class SvgDoc {
  final StringBuffer body = StringBuffer();
  final StringBuffer defs = StringBuffer();
  List<String> strings = const [];
  List<List<String>> stringLists = const [];
  List<List<double>> floatLists = const [];
  List<double> floatValues = const [];
  List<SIImageData> images = const [];
  double? width;
  double? height;
  int gradientId = 0;
  int paths = 0;
  int imageCount = 0;
  int groups = 0;

  String finish() {
    final w = width ?? 100;
    final h = height ?? 100;
    return '<svg xmlns="http://www.w3.org/2000/svg" width="${num(w)}" height="${num(h)}" viewBox="0 0 ${num(w)} ${num(h)}">'
        '${defs.isEmpty ? '' : '<defs>$defs</defs>'}$body</svg>\n';
  }
}

class SvgVisitor implements SIVisitor<CompactChildData, SIImageData, SvgDoc> {
  final SvgDoc doc;
  SvgVisitor(this.doc);

  @override
  SvgDoc get initial => doc;

  @override
  SvgDoc init(SvgDoc collector, List<SIImageData> images, List<String> strings,
      List<List<double>> floatLists, List<List<String>> stringLists,
      List<double> floatValues, CMap<double>? _) {
    doc.images = images;
    doc.strings = strings;
    doc.floatLists = floatLists;
    doc.stringLists = stringLists;
    doc.floatValues = floatValues;
    return collector;
  }

  @override
  SvgDoc path(SvgDoc collector, CompactChildData data, SIPaint paint) {
    final builder = SvgPathBuilder();
    CompactPathParser(data, builder).parse();
    doc.body.write('<path d="${esc(builder.result)}" ${style(paint)}/>');
    doc.paths++;
    return collector;
  }

  @override
  SvgDoc group(SvgDoc collector, Affine? transform, int? alpha, SIBlendMode blend) {
    final attrs = <String>[];
    if (transform != null) attrs.add('transform="${matrix(transform)}"');
    if (alpha != null) attrs.add('opacity="${num(alpha / 255)}"');
    if (blend != SIBlendMode.normal) attrs.add('style="mix-blend-mode:${blend.name}"');
    doc.body.write('<g${attrs.isEmpty ? '' : ' ${attrs.join(' ')}'}>');
    doc.groups++;
    return collector;
  }

  @override
  SvgDoc endGroup(SvgDoc collector) { doc.body.write('</g>'); return collector; }

  @override
  SvgDoc clipPath(SvgDoc collector, CompactChildData data) {
    final builder = SvgPathBuilder();
    CompactPathParser(data, builder).parse();
    doc.body.write('<path data-recovered-clip="true" d="${esc(builder.result)}" fill="none"/>');
    return collector;
  }

  @override
  SvgDoc masked(SvgDoc collector, RectT? bounds, bool usesLuma) {
    doc.body.write('<g data-recovered-mask="${usesLuma ? 'luma' : 'alpha'}">');
    return collector;
  }

  @override
  SvgDoc maskedChild(SvgDoc collector) => collector;

  @override
  SvgDoc endMasked(SvgDoc collector) { doc.body.write('</g>'); return collector; }

  @override
  SvgDoc image(SvgDoc collector, int imageIndex) {
    final image = doc.images[imageIndex];
    final mime = image.encoded.length >= 8 && image.encoded[0] == 0x89 ? 'image/png' : 'application/octet-stream';
    doc.body.write('<image x="${num(image.x)}" y="${num(image.y)}" width="${num(image.width)}" height="${num(image.height)}" href="data:$mime;base64,${base64Encode(image.encoded)}"/>');
    doc.imageCount++;
    return collector;
  }

  @override
  SvgDoc legacyText(SvgDoc collector, int xIndex, int yIndex, int textIndex,
      SITextAttributes attributes, int? _, SIPaint paint) {
    final xs = doc.floatLists[xIndex];
    final ys = doc.floatLists[yIndex];
    final x = xs.isEmpty ? 0.0 : xs.first;
    final y = ys.isEmpty ? 0.0 : ys.first;
    doc.body.write('<text x="${num(x)}" y="${num(y)}" ${textStyle(attributes)} ${style(paint)}>${esc(doc.strings[textIndex])}</text>');
    return collector;
  }

  @override
  SvgDoc text(SvgDoc collector) { doc.body.write('<text>'); return collector; }

  @override
  SvgDoc textSpan(SvgDoc collector, int dxIndex, int dyIndex, int textIndex,
      SITextAttributes attributes, int? _, int __, SIPaint paint) {
    final dx = doc.floatLists[dxIndex].isEmpty ? 0.0 : doc.floatLists[dxIndex].first;
    final dy = doc.floatLists[dyIndex].isEmpty ? 0.0 : doc.floatLists[dyIndex].first;
    doc.body.write('<tspan dx="${num(dx)}" dy="${num(dy)}" ${textStyle(attributes)} ${style(paint)}>${esc(doc.strings[textIndex])}</tspan>');
    return collector;
  }

  @override
  SvgDoc textMultiSpanChunk(SvgDoc collector, int dxIndex, int dyIndex, SITextAnchor anchor) => collector;

  @override
  SvgDoc textEnd(SvgDoc collector) { doc.body.write('</text>'); return collector; }

  @override
  SvgDoc exportedID(SvgDoc collector, int idIndex) { doc.body.write('<g id="${esc(doc.strings[idIndex])}">'); return collector; }

  @override
  SvgDoc endExportedID(SvgDoc collector) { doc.body.write('</g>'); return collector; }

  @override
  void traversalDone() {}

  String textStyle(SITextAttributes a) => 'font-size="${num(a.fontSize)}" font-style="${a.fontStyle.name}" font-weight="${100 + a.fontWeight.index * 100}" text-anchor="${a.textAnchor.name}"';

  String style(SIPaint paint) {
    final fill = color(paint.fillColor);
    final stroke = color(paint.strokeColor);
    final values = ['fill="$fill"', 'stroke="$stroke"', 'stroke-width="${num(paint.strokeWidth)}"', 'stroke-miterlimit="${num(paint.strokeMiterLimit)}"', 'stroke-linejoin="${paint.strokeJoin.name}"', 'stroke-linecap="${paint.strokeCap.name}"', 'fill-rule="${paint.fillType == SIFillType.evenOdd ? 'evenodd' : 'nonzero'}"'];
    if (paint.strokeDashArray != null) values.add('stroke-dasharray="${paint.strokeDashArray!.map(num).join(' ')}"');
    if (paint.strokeDashOffset != null) values.add('stroke-dashoffset="${num(paint.strokeDashOffset!)}"');
    return values.join(' ');
  }

  String color(SIColor value) {
    String result = 'none';
    value.accept(SIColorVisitor(
      value: (c) { result = colorValue(c.argb); },
      none: () {},
      current: () { result = 'currentColor'; },
      linearGradient: (g) { result = linear(g); },
      radialGradient: (g) { result = radial(g); },
      sweepGradient: (_) { result = 'none'; },
    ));
    return result;
  }

  String colorValue(int argb) {
    final alpha = (argb >> 24) & 0xff;
    final rgb = argb & 0xffffff;
    return '#${rgb.toRadixString(16).padLeft(6, '0')}${alpha == 255 ? '' : '" fill-opacity="${num(alpha / 255)}'}';
  }

  String linear(SILinearGradientColor g) {
    final id = 'gradient${doc.gradientId++}';
    doc.defs.write('<linearGradient id="$id" x1="${num(g.x1)}" y1="${num(g.y1)}" x2="${num(g.x2)}" y2="${num(g.y2)}" spreadMethod="${g.spreadMethod.name}">${stops(g)}</linearGradient>');
    return 'url(#$id)';
  }

  String radial(SIRadialGradientColor g) {
    final id = 'gradient${doc.gradientId++}';
    doc.defs.write('<radialGradient id="$id" cx="${num(g.cx)}" cy="${num(g.cy)}" fx="${num(g.fx)}" fy="${num(g.fy)}" r="${num(g.r)}" spreadMethod="${g.spreadMethod.name}">${stops(g)}</radialGradient>');
    return 'url(#$id)';
  }

  String stops(SIGradientColor g) => List<String>.generate(g.stops.length, (i) => '<stop offset="${num(g.stops[i])}" stop-color="${color(g.colors[i])}"/>').join();

  String matrix(Affine m) => [m.get(0, 0), m.get(1, 0), m.get(0, 1), m.get(1, 1), m.get(0, 2), m.get(1, 2)].map(num).join(' ');
}

Future<void> main(List<String> arguments) async {
  if (arguments.length != 2) {
    stderr.writeln('usage: decode_si_resources.dart <input-dir> <output-dir>');
    exitCode = 2;
    return;
  }
  final input = Directory(arguments[0]);
  final output = Directory(arguments[1])..createSync(recursive: true);
  var decoded = 0;
  final failures = <Map<String, String>>[];
  await for (final entity in input.list(recursive: true, followLinks: false)) {
    if (entity is! File || !entity.path.toLowerCase().endsWith('.si')) continue;
    final relative = entity.path.substring(input.path.length + 1);
    try {
      final parsed = parseSI(await entity.readAsBytes());
      final doc = SvgDoc()..width = parsed.width..height = parsed.height;
      final traverser = CompactTraverser<SvgDoc, SIImageData>(
        fileVersion: parsed.version,
        bigFloats: parsed.bigFloats,
        visiteeChildren: parsed.children,
        visiteeArgs: parsed.args,
        visiteeTransforms: parsed.transforms,
        visiteeNumPaths: parsed.numPaths,
        visiteeNumPaints: parsed.numPaints,
        visitor: SvgVisitor(doc),
        strings: parsed.strings,
        stringLists: parsed.stringLists,
        floatLists: parsed.floatLists,
        floatValues: parsed.floatValues,
        images: parsed.images,
      );
      traverser.traverse(doc);
      final target = File('${output.path}/${relative.substring(0, relative.length - 3)}.svg')..createSync(recursive: true);
      await target.writeAsString(doc.finish());
      decoded++;
    } catch (error) {
      failures.add({'source': relative, 'error': '$error'});
    }
  }
  final index = {'decoded': decoded, 'failures': failures};
  await File('${output.path}/index.json').writeAsString(const JsonEncoder.withIndent('  ').convert(index) + '\n');
  stdout.writeln(jsonEncode({'decoded': decoded, 'failures': failures.length}));
}
