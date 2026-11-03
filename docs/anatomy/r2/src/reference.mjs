// Millimetres in enclosure coordinates. Source: the repository's read-only Taco
// V1.61 STEP, rotated 180 degrees about Y and translated by [72.1, 120, 135],
// exactly as hardware/enclosure/r1/src/design.py::references().
// Socket interiors remain schematic; the manufacturer's housing envelopes,
// connector order, board outline, hole positions and SATA datum are preserved.
export const BOARD = Object.freeze({
  bottom:133.4, top:135, front:35.6795,
  outline:[[120.2,35.7],[120.8693,35.7343],[121.505,35.9466],[122.0606,36.3213],[122.4956,36.8312],[122.7781,37.4389],[122.8876,38.1001],[122.8876,116.75],[122.8271,117.5942],[122.5802,118.4038],[122.1592,119.1381],[121.5852,119.7602],[120.8871,120.2388],[120.1,120.55],[12.9,120.55],[11.9455,120.4366],[11.0538,120.0779],[10.2866,119.4989],[9.6972,118.7396],[9.3264,117.8528],[9.2,116.9],[9.2,39.5489],[9.2553,38.5093],[9.611,37.5309],[10.2362,36.6985],[11.0768,36.0843],[12.0598,35.7416],[13.1,35.7]],
  holes:[[20.1,60.2],[12.9,116.95],[105,60.2],[119.45,116.9]],
  sata:{y:54.7,depth:43.5587,bottom:122.7003,width:4.8999},
});
export const PORTS = Object.freeze([
  {id:'ethernet-1g',kind:'rj45',bounds:[10.65,33.05,131.05,26.88,54.3,148.35]},
  {id:'ethernet-2.5g',kind:'rj45',bounds:[31.65,33.05,131.05,47.88,54.3,148.35]},
  {id:'usb-a',kind:'usb-a',bounds:[51.04,33,131.8024,66.71,50.46,150.5]},
  {id:'hdmi',kind:'hdmi',bounds:[70.622,33.4,132.975,85.622,45.4,141.25]},
  {id:'usb-c',kind:'usb-c',bounds:[88.945,33.4401,131.0076,96.345,40.8401,142.0076]},
  {id:'dc',kind:'dc',bounds:[107.515,34.35,132.1991,117.515,47.35,145.4]},
]);
