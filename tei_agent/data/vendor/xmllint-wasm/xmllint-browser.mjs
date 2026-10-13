var Module = (() => {
  var _scriptName = typeof document != 'undefined' ? document.currentScript?.src : undefined;
  
  return (
async function(moduleArg = {}) {
  var moduleRtn;

var h=moduleArg,aa,ba,da=new Promise((a,b)=>{aa=a;ba=b});h.preRun=function(){h.inputFiles.forEach(function(a){var b="/"+a.fileName,c=b.substring(0,b.lastIndexOf("/"));1<c.length&&ea("/",c.substring(1),!0,!0);c=a.contents;a={};a.flags=a.flags||577;b=k(b,a.flags,a.mode);if("string"==typeof c){var d=new Uint8Array(ha(c)+1);c=ia(c,d,0,d.length);n(b,d,0,c,void 0,a.ua)}else if(ArrayBuffer.isView(c))n(b,c,0,c.byteLength,void 0,a.ua);else throw Error("Unsupported data type");t(b)})};
var ja={...h},ka=[],la="./this.program",v="",ma;"undefined"!=typeof document&&document.currentScript&&(v=document.currentScript.src);_scriptName&&(v=_scriptName);v.startsWith("blob:")?v="":v=v.slice(0,v.replace(/[?#].*/,"").lastIndexOf("/")+1);ma=async a=>{a=await fetch(a,{credentials:"same-origin"});if(a.ok)return a.arrayBuffer();throw Error(a.status+" : "+a.url);};var na=h.print||console.log.bind(console),x=h.printErr||console.error.bind(console);Object.assign(h,ja);ja=null;h.arguments&&(ka=h.arguments);
h.thisProgram&&(la=h.thisProgram);var y=h.wasmBinary,z,oa=!1,A,B,pa,C,D,E;function qa(){var a=z.buffer;h.HEAP8=A=new Int8Array(a);h.HEAP16=pa=new Int16Array(a);h.HEAPU8=B=new Uint8Array(a);h.HEAPU16=new Uint16Array(a);h.HEAP32=C=new Int32Array(a);h.HEAPU32=D=new Uint32Array(a);h.HEAPF32=new Float32Array(a);h.HEAPF64=new Float64Array(a);h.HEAP64=E=new BigInt64Array(a);h.HEAPU64=new BigUint64Array(a)}h.wasmMemory?z=h.wasmMemory:z=new WebAssembly.Memory({initial:(h.INITIAL_MEMORY||16777216)/65536,maximum:65536});
qa();var F=0,G=null;function ra(){F++;h.monitorRunDependencies?.(F)}function sa(){F--;h.monitorRunDependencies?.(F);if(0==F&&G){var a=G;G=null;a()}}var ta;async function ua(a){if(!y)try{var b=await ma(a);return new Uint8Array(b)}catch{}if(a==ta&&y)a=new Uint8Array(y);else throw"both async and sync fetching of the wasm failed";return a}
async function va(a,b){try{var c=await ua(a);return await WebAssembly.instantiate(c,b)}catch(d){throw x(`failed to asynchronously prepare wasm: ${d}`),a=d,h.onAbort?.(a),a="Aborted("+a+")",x(a),oa=!0,a=new WebAssembly.RuntimeError(a+". Build with -sASSERTIONS for more info."),ba(a),a;}}
async function wa(a){var b=ta;if(!y&&"function"==typeof WebAssembly.instantiateStreaming)try{var c=fetch(b,{credentials:"same-origin"});return await WebAssembly.instantiateStreaming(c,a)}catch(d){x(`wasm streaming compile failed: ${d}`),x("falling back to ArrayBuffer instantiation")}return va(b,a)}class xa{name="ExitStatus";constructor(a){this.message=`Program terminated with exit(${a})`;this.status=a}}
var ya=a=>{for(;0<a.length;)a.shift()(h)},za=[],Aa=[],Ba=()=>{var a=h.preRun.shift();Aa.unshift(a)},Da=h.noExitRuntime||!1,Ea=(a,b)=>{for(var c=0,d=a.length-1;0<=d;d--){var e=a[d];"."===e?a.splice(d,1):".."===e?(a.splice(d,1),c++):c&&(a.splice(d,1),c--)}if(b)for(;c;c--)a.unshift("..");return a},H=a=>{var b="/"===a.charAt(0),c="/"===a.slice(-1);(a=Ea(a.split("/").filter(d=>!!d),!b).join("/"))||b||(a=".");a&&c&&(a+="/");return(b?"/":"")+a},Fa=a=>{var b=/^(\/?|)([\s\S]*?)((?:\.{1,2}|[^\/]+?|)(\.[^.\/]*|))(?:[\/]*)$/.exec(a).slice(1);
a=b[0];b=b[1];if(!a&&!b)return".";b&&=b.slice(0,-1);return a+b},Ga=()=>a=>crypto.getRandomValues(a),Ha=a=>{(Ha=Ga())(a)},Ia=(...a)=>{for(var b="",c=!1,d=a.length-1;-1<=d&&!c;d--){c=0<=d?a[d]:"/";if("string"!=typeof c)throw new TypeError("Arguments to path.resolve must be strings");if(!c)return"";b=c+"/"+b;c="/"===c.charAt(0)}b=Ea(b.split("/").filter(e=>!!e),!c).join("/");return(c?"/":"")+b||"."},Ja="undefined"!=typeof TextDecoder?new TextDecoder:void 0,I=(a,b=0)=>{b>>>=0;for(var c=b+NaN,d=b;a[d]&&
!(d>=c);)++d;if(16<d-b&&a.buffer&&Ja)return Ja.decode(a.subarray(b,d));for(c="";b<d;){var e=a[b++];if(e&128){var f=a[b++]&63;if(192==(e&224))c+=String.fromCharCode((e&31)<<6|f);else{var g=a[b++]&63;e=224==(e&240)?(e&15)<<12|f<<6|g:(e&7)<<18|f<<12|g<<6|a[b++]&63;65536>e?c+=String.fromCharCode(e):(e-=65536,c+=String.fromCharCode(55296|e>>10,56320|e&1023))}}else c+=String.fromCharCode(e)}return c},Ka=[],ha=a=>{for(var b=0,c=0;c<a.length;++c){var d=a.charCodeAt(c);127>=d?b++:2047>=d?b+=2:55296<=d&&57343>=
d?(b+=4,++c):b+=3}return b},ia=(a,b,c,d)=>{c>>>=0;if(!(0<d))return 0;var e=c;d=c+d-1;for(var f=0;f<a.length;++f){var g=a.charCodeAt(f);if(55296<=g&&57343>=g){var l=a.charCodeAt(++f);g=65536+((g&1023)<<10)|l&1023}if(127>=g){if(c>=d)break;b[c++>>>0]=g}else{if(2047>=g){if(c+1>=d)break;b[c++>>>0]=192|g>>6}else{if(65535>=g){if(c+2>=d)break;b[c++>>>0]=224|g>>12}else{if(c+3>=d)break;b[c++>>>0]=240|g>>18;b[c++>>>0]=128|g>>12&63}b[c++>>>0]=128|g>>6&63}b[c++>>>0]=128|g&63}}b[c>>>0]=0;return c-e},La=[];
function Ma(a,b){La[a]={input:[],output:[],P:b};Na(a,Oa)}
var Oa={open(a){var b=La[a.node.W];if(!b)throw new J(43);a.D=b;a.seekable=!1},close(a){a.D.P.$(a.D)},$(a){a.D.P.$(a.D)},read(a,b,c,d){if(!a.D||!a.D.P.la)throw new J(60);for(var e=0,f=0;f<d;f++){try{var g=a.D.P.la(a.D)}catch(l){throw new J(29);}if(void 0===g&&0===e)throw new J(6);if(null===g||void 0===g)break;e++;b[c+f]=g}e&&(a.node.R=Date.now());return e},write(a,b,c,d){if(!a.D||!a.D.P.ga)throw new J(60);try{for(var e=0;e<d;e++)a.D.P.ga(a.D,b[c+e])}catch(f){throw new J(29);}d&&(a.node.I=a.node.H=
Date.now());return e}},Pa={la(){a:{if(!Ka.length){var a=null;"undefined"!=typeof window&&"function"==typeof window.prompt&&(a=window.prompt("Input: "),null!==a&&(a+="\n"));if(!a){var b=null;break a}b=Array(ha(a)+1);a=ia(a,b,0,b.length);b.length=a;Ka=b}b=Ka.shift()}return b},ga(a,b){null===b||10===b?(na(I(a.output)),a.output=[]):0!=b&&a.output.push(b)},$(a){0<a.output?.length&&(na(I(a.output)),a.output=[])},za(){return{Ja:25856,La:5,Ia:191,Ka:35387,Ha:[3,28,127,21,4,0,1,0,17,19,26,0,18,15,23,22,0,
0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]}},Aa(){return 0},Ba(){return[24,80]}},Qa={ga(a,b){null===b||10===b?(x(I(a.output)),a.output=[]):0!=b&&a.output.push(b)},$(a){0<a.output?.length&&(x(I(a.output)),a.output=[])}},Sa=a=>{a=65536*Math.ceil(a/65536);var b=Ra(65536,a);b&&B.fill(0,b,b+a);return b},K={K:null,O(){return K.createNode(null,"/",16895,0)},createNode(a,b,c,d){if(24576===(c&61440)||4096===(c&61440))throw new J(63);K.K||(K.K={dir:{node:{N:K.C.N,L:K.C.L,T:K.C.T,aa:K.C.aa,qa:K.C.qa,da:K.C.da,ra:K.C.ra,
ha:K.C.ha,ca:K.C.ca},stream:{J:K.B.J}},file:{node:{N:K.C.N,L:K.C.L},stream:{J:K.B.J,read:K.B.read,write:K.B.write,U:K.B.U,ba:K.B.ba}},link:{node:{N:K.C.N,L:K.C.L,X:K.C.X},stream:{}},ja:{node:{N:K.C.N,L:K.C.L},stream:Ta}});c=Ua(a,b,c,d);L(c.mode)?(c.C=K.K.dir.node,c.B=K.K.dir.stream,c.A={}):32768===(c.mode&61440)?(c.C=K.K.file.node,c.B=K.K.file.stream,c.F=0,c.A=null):40960===(c.mode&61440)?(c.C=K.K.link.node,c.B=K.K.link.stream):8192===(c.mode&61440)&&(c.C=K.K.ja.node,c.B=K.K.ja.stream);c.R=c.I=c.H=
Date.now();a&&(a.A[b]=c,a.R=a.I=a.H=c.R);return c},Oa(a){return a.A?a.A.subarray?a.A.subarray(0,a.F):new Uint8Array(a.A):new Uint8Array(0)},C:{N(a){var b={};b.va=8192===(a.mode&61440)?a.id:1;b.xa=a.id;b.mode=a.mode;b.Ea=1;b.uid=0;b.wa=0;b.W=a.W;L(a.mode)?b.size=4096:32768===(a.mode&61440)?b.size=a.F:40960===(a.mode&61440)?b.size=a.link.length:b.size=0;b.R=new Date(a.R);b.I=new Date(a.I);b.H=new Date(a.H);b.sa=4096;b.ta=Math.ceil(b.size/b.sa);return b},L(a,b){for(var c of["mode","atime","mtime","ctime"])null!=
b[c]&&(a[c]=b[c]);void 0!==b.size&&(b=b.size,a.F!=b&&(0==b?(a.A=null,a.F=0):(c=a.A,a.A=new Uint8Array(b),c&&a.A.set(c.subarray(0,Math.min(b,a.F))),a.F=b)))},T(){throw K.ka;},aa(a,b,c,d){return K.createNode(a,b,c,d)},qa(a,b,c){try{var d=M(b,c)}catch(f){}if(d){if(L(a.mode))for(var e in d.A)throw new J(55);Va(d)}delete a.parent.A[a.name];b.A[c]=a;a.name=c;b.H=b.I=a.parent.H=a.parent.I=Date.now()},da(a,b){delete a.A[b];a.H=a.I=Date.now()},ra(a,b){var c=M(a,b),d;for(d in c.A)throw new J(55);delete a.A[b];
a.H=a.I=Date.now()},ha(a){return[".","..",...Object.keys(a.A)]},ca(a,b,c){a=K.createNode(a,b,41471,0);a.link=c;return a},X(a){if(40960!==(a.mode&61440))throw new J(28);return a.link}},B:{read(a,b,c,d,e){var f=a.node.A;if(e>=a.node.F)return 0;a=Math.min(a.node.F-e,d);if(8<a&&f.subarray)b.set(f.subarray(e,e+a),c);else for(d=0;d<a;d++)b[c+d]=f[e+d];return a},write(a,b,c,d,e,f){b.buffer===A.buffer&&(f=!1);if(!d)return 0;a=a.node;a.I=a.H=Date.now();if(b.subarray&&(!a.A||a.A.subarray)){if(f)return a.A=
b.subarray(c,c+d),a.F=d;if(0===a.F&&0===e)return a.A=b.slice(c,c+d),a.F=d;if(e+d<=a.F)return a.A.set(b.subarray(c,c+d),e),d}f=e+d;var g=a.A?a.A.length:0;g>=f||(f=Math.max(f,g*(1048576>g?2:1.125)>>>0),0!=g&&(f=Math.max(f,256)),g=a.A,a.A=new Uint8Array(f),0<a.F&&a.A.set(g.subarray(0,a.F),0));if(a.A.subarray&&b.subarray)a.A.set(b.subarray(c,c+d),e);else for(f=0;f<d;f++)a.A[e+f]=b[c+f];a.F=Math.max(a.F,e+d);return d},J(a,b,c){1===c?b+=a.position:2===c&&32768===(a.node.mode&61440)&&(b+=a.node.F);if(0>
b)throw new J(28);return b},U(a,b,c,d,e){if(32768!==(a.node.mode&61440))throw new J(43);a=a.node.A;if(e&2||!a||a.buffer!==A.buffer){d=!0;e=Sa(b);if(!e)throw new J(48);if(a){if(0<c||c+b<a.length)a.subarray?a=a.subarray(c,c+b):a=Array.prototype.slice.call(a,c,c+b);A.set(a,e>>>0)}}else d=!1,e=a.byteOffset;return{pa:e,ia:d}},ba(a,b,c,d){K.B.write(a,b,0,d,c,!1);return 0}}},Wa=async a=>{a=await ma(a);return new Uint8Array(a)},Xa=h.preloadPlugins||[],Ya=(a,b,c,d)=>{"undefined"!=typeof Browser&&Browser.Pa();
var e=!1;Xa.forEach(f=>{!e&&f.canHandle(b)&&(f.handle(a,b,c,d),e=!0)});return e},$a=(a,b,c,d,e,f,g,l,p,m)=>{function r(w){function T(ca){m?.();l||Za(a,b,ca,d,e,p);f?.();sa(u)}Ya(w,q,T,()=>{g?.();sa(u)})||T(w)}var q=b?Ia(H(a+"/"+b)):a,u=`cp ${q}`;ra(u);"string"==typeof c?Wa(c).then(r,g):r(c)},ab=(a,b)=>{var c=0;a&&(c|=365);b&&(c|=146);return c},bb=null,cb={},N=[],db=1,O=null,eb=!1,fb=!0,gb={},J=class{name="ErrnoError";constructor(a){this.G=a}},hb=class{Y={};node=null;get flags(){return this.Y.flags}set flags(a){this.Y.flags=
a}get position(){return this.Y.position}set position(a){this.Y.position=a}},ib=class{C={};B={};V=null;constructor(a,b,c,d){a||=this;this.parent=a;this.O=a.O;this.id=db++;this.name=b;this.mode=c;this.W=d;this.R=this.I=this.H=Date.now()}get read(){return 365===(this.mode&365)}set read(a){a?this.mode|=365:this.mode&=-366}get write(){return 146===(this.mode&146)}set write(a){a?this.mode|=146:this.mode&=-147}get Ca(){return L(this.mode)}get ma(){return 8192===(this.mode&61440)}};
function P(a,b={}){if(!a)throw new J(44);b.ea??(b.ea=!0);"/"===a.charAt(0)||(a="//"+a);var c=0;a:for(;40>c;c++){a=a.split("/").filter(l=>!!l);for(var d=bb,e="/",f=0;f<a.length;f++){var g=f===a.length-1;if(g&&b.parent)break;if("."!==a[f])if(".."===a[f])e=Fa(e),d=d.parent;else{e=H(e+"/"+a[f]);try{d=M(d,a[f])}catch(l){if(44===l?.G&&g&&b.Fa)return{path:e};throw l;}!d.V||g&&!b.ea||(d=d.V.root);if(40960===(d.mode&61440)&&(!g||b.Z)){if(!d.C.X)throw new J(52);d=d.C.X(d);"/"===d.charAt(0)||(d=Fa(e)+"/"+d);
a=d+"/"+a.slice(f+1).join("/");continue a}}}return{path:e,node:d}}throw new J(32);}function Q(a){for(var b;;){if(a===a.parent)return a=a.O.oa,b?"/"!==a[a.length-1]?`${a}/${b}`:a+b:a;b=b?`${a.name}/${b}`:a.name;a=a.parent}}function jb(a,b){for(var c=0,d=0;d<b.length;d++)c=(c<<5)-c+b.charCodeAt(d)|0;return(a+c>>>0)%O.length}function Va(a){var b=jb(a.parent.id,a.name);if(O[b]===a)O[b]=a.S;else for(b=O[b];b;){if(b.S===a){b.S=a.S;break}b=b.S}}
function M(a,b){var c=L(a.mode)?(c=R(a,"x"))?c:a.C.T?0:2:54;if(c)throw new J(c);for(c=O[jb(a.id,b)];c;c=c.S){var d=c.name;if(c.parent.id===a.id&&d===b)return c}return a.C.T(a,b)}function Ua(a,b,c,d){a=new ib(a,b,c,d);b=jb(a.parent.id,a.name);a.S=O[b];return O[b]=a}function L(a){return 16384===(a&61440)}function kb(a){var b=["r","w","rw"][a&3];a&512&&(b+="w");return b}
function R(a,b){if(fb)return 0;if(!b.includes("r")||a.mode&292){if(b.includes("w")&&!(a.mode&146)||b.includes("x")&&!(a.mode&73))return 2}else return 2;return 0}function lb(a,b){if(!L(a.mode))return 54;try{return M(a,b),20}catch(c){}return R(a,"wx")}function mb(a){if(!a)throw new J(63);return a}function S(a){a=N[a];if(!a)throw new J(8);return a}function nb(a,b=-1){a=Object.assign(new hb,a);if(-1==b)a:{for(b=0;4096>=b;b++)if(!N[b])break a;throw new J(33);}a.M=b;return N[b]=a}
function ob(a,b=-1){a=nb(a,b);a.B?.Na?.(a);return a}function qb(a,b){var c=null?.B.L,d=c?null:a;c??=a.C.L;mb(c);c(d,b)}var Ta={open(a){a.B=cb[a.node.W].B;a.B.open?.(a)},J(){throw new J(70);}};function Na(a,b){cb[a]={B:b}}function rb(a,b){var c="/"===b;if(c&&bb)throw new J(10);if(!c&&b){var d=P(b,{ea:!1});b=d.path;d=d.node;if(d.V)throw new J(10);if(!L(d.mode))throw new J(54);}b={type:a,Qa:{},oa:b,Da:[]};a=a.O(b);a.O=b;b.root=a;c?bb=a:d&&(d.V=b,d.O&&d.O.Da.push(b))}
function sb(a,b,c){var d=P(a,{parent:!0}).node;a=a&&a.match(/([^\/]+|\/)\/*$/)[1];if(!a)throw new J(28);if("."===a||".."===a)throw new J(20);var e=lb(d,a);if(e)throw new J(e);if(!d.C.aa)throw new J(63);return d.C.aa(d,a,b,c)}function tb(a,b=438){return sb(a,b&4095|32768,0)}function U(a){return sb(a,16895,0)}function ub(a,b,c){"undefined"==typeof c&&(c=b,b=438);return sb(a,b|8192,c)}
function vb(a,b){if(!Ia(a))throw new J(44);var c=P(b,{parent:!0}).node;if(!c)throw new J(44);b=b&&b.match(/([^\/]+|\/)\/*$/)[1];var d=lb(c,b);if(d)throw new J(d);if(!c.C.ca)throw new J(63);c.C.ca(c,b,a)}function wb(a){var b=P(a,{parent:!0}).node;if(!b)throw new J(44);a=a&&a.match(/([^\/]+|\/)\/*$/)[1];var c=M(b,a);a:{try{var d=M(b,a)}catch(f){d=f.G;break a}var e=R(b,"wx");d=e?e:L(d.mode)?31:0}if(d)throw new J(d);if(!b.C.da)throw new J(63);if(c.V)throw new J(10);b.C.da(b,a);Va(c)}
function xb(a,b){a="string"==typeof a?P(a,{Z:!0}).node:a;qb(a,{mode:b&4095|a.mode&-4096,H:Date.now(),Ma:void 0})}
function k(a,b,c=438){if(""===a)throw new J(44);if("string"==typeof b){var d={r:0,"r+":2,w:577,"w+":578,a:1089,"a+":1090}[b];if("undefined"==typeof d)throw Error(`Unknown file open mode: ${b}`);b=d}c=b&64?c&4095|32768:0;if("object"==typeof a)d=a;else{var e=a.endsWith("/");a=P(a,{Z:!(b&131072),Fa:!0});d=a.node;a=a.path}var f=!1;if(b&64)if(d){if(b&128)throw new J(20);}else{if(e)throw new J(31);d=sb(a,c|511,0);f=!0}if(!d)throw new J(44);8192===(d.mode&61440)&&(b&=-513);if(b&65536&&!L(d.mode))throw new J(54);
if(!f&&(e=d?40960===(d.mode&61440)?32:L(d.mode)&&("r"!==kb(b)||b&576)?31:R(d,kb(b)):44))throw new J(e);if(b&512&&!f){e=d;e="string"==typeof e?P(e,{Z:!0}).node:e;if(L(e.mode))throw new J(31);if(32768!==(e.mode&61440))throw new J(28);var g=R(e,"w");if(g)throw new J(g);qb(e,{size:0,timestamp:Date.now()})}b&=-131713;e=nb({node:d,path:Q(d),flags:b,seekable:!0,position:0,B:d.B,Ga:[],error:!1});e.B.open&&e.B.open(e);f&&xb(d,c&511);!h.logReadFiles||b&1||a in gb||(gb[a]=1);return e}
function t(a){if(null===a.M)throw new J(8);a.fa&&(a.fa=null);try{a.B.close&&a.B.close(a)}catch(b){throw b;}finally{N[a.M]=null}a.M=null}function yb(a,b,c){if(null===a.M)throw new J(8);if(!a.seekable||!a.B.J)throw new J(70);if(0!=c&&1!=c&&2!=c)throw new J(28);a.position=a.B.J(a,b,c);a.Ga=[]}
function n(a,b,c,d,e,f){if(0>d||0>e)throw new J(28);if(null===a.M)throw new J(8);if(0===(a.flags&2097155))throw new J(8);if(L(a.node.mode))throw new J(31);if(!a.B.write)throw new J(28);a.seekable&&a.flags&1024&&yb(a,0,2);var g="undefined"!=typeof e;if(!g)e=a.position;else if(!a.seekable)throw new J(70);b=a.B.write(a,b,c,d,e,f);g||(a.position+=b);return b}
function ea(a,b){a="string"==typeof a?a:Q(a);for(b=b.split("/").reverse();b.length;){var c=b.pop();if(c){var d=H(a+"/"+c);try{U(d)}catch(e){if(20!=e.G)throw e;}a=d}}return d}function zb(a,b,c,d){a=H(("string"==typeof a?a:Q(a))+"/"+b);return tb(a,ab(c,d))}
function Za(a,b,c,d,e,f){var g=b;a&&(a="string"==typeof a?a:Q(a),g=b?H(a+"/"+b):a);a=ab(d,e);g=tb(g,a);if(c){if("string"==typeof c){b=Array(c.length);d=0;for(e=c.length;d<e;++d)b[d]=c.charCodeAt(d);c=b}xb(g,a|146);b=k(g,577);n(b,c,0,c.length,0,f);t(b);xb(g,a)}}
function V(a,b,c,d){a=H(("string"==typeof a?a:Q(a))+"/"+b);b=ab(!!c,!!d);V.na??(V.na=64);var e=V.na++<<8|0;Na(e,{open(f){f.seekable=!1},close(){d?.buffer?.length&&d(10)},read(f,g,l,p){for(var m=0,r=0;r<p;r++){try{var q=c()}catch(u){throw new J(29);}if(void 0===q&&0===m)throw new J(6);if(null===q||void 0===q)break;m++;g[l+r]=q}m&&(f.node.R=Date.now());return m},write(f,g,l,p){for(var m=0;m<p;m++)try{d(g[l+m])}catch(r){throw new J(29);}p&&(f.node.I=f.node.H=Date.now());return m}});return ub(a,b,e)}
function Ab(a){if(!(a.ma||a.Ca||a.link||a.A)){if("undefined"!=typeof XMLHttpRequest)throw Error("Lazy loading should have been performed (contents set) in createLazyFile, but it was not. Lazy loading only works in web workers. Use --embed-file or --preload-file in emcc on the main thread.");try{a.A=(void 0)(a.url),a.F=a.A.length}catch(b){throw new J(29);}}}
function Bb(a,b,c,d,e){function f(p,m,r,q,u){p=p.node.A;if(u>=p.length)return 0;q=Math.min(p.length-u,q);if(p.slice)for(var w=0;w<q;w++)m[r+w]=p[u+w];else for(w=0;w<q;w++)m[r+w]=p.get(u+w);return q}if("undefined"!=typeof XMLHttpRequest)throw"Cannot do synchronous binary XHRs outside webworkers in modern browsers. Use --embed-file or --preload-file in emcc";c={ma:!1,url:c};var g=zb(a,b,d,e);c.A?g.A=c.A:c.url&&(g.A=null,g.url=c.url);Object.defineProperties(g,{F:{get:function(){return this.A.length}}});
var l={};Object.keys(g.B).forEach(p=>{var m=g.B[p];l[p]=(...r)=>{Ab(g);return m(...r)}});l.read=(p,m,r,q,u)=>{Ab(g);return f(p,m,r,q,u)};l.U=(p,m,r)=>{Ab(g);var q=Sa(m);if(!q)throw new J(48);f(p,A,q,m,r);return{pa:q,ia:!0}};g.B=l;return g}
var W={},Cb=a=>(a>>>=0)?I(B,a):"",X=void 0,Y=()=>{var a=C[+X>>>2>>>0];X+=4;return a},Db={},Fb=()=>{if(!Eb){var a={USER:"web_user",LOGNAME:"web_user",PATH:"/",PWD:"/",HOME:"/home/web_user",LANG:("object"==typeof navigator&&navigator.languages&&navigator.languages[0]||"C").replace("-","_")+".UTF-8",_:la||"./this.program"},b;for(b in Db)void 0===Db[b]?delete a[b]:a[b]=Db[b];var c=[];for(b in a)c.push(`${b}=${a[b]}`);Eb=c}return Eb},Eb,Ib=a=>{if(!Da){Gb();eb=!1;Hb(0);for(var b of N)b&&t(b)}Da||(h.onExit?.(a),
oa=!0);throw new xa(a);};O=Array(4096);rb(K,"/");U("/tmp");U("/home");U("/home/web_user");(function(){U("/dev");Na(259,{read:()=>0,write:(d,e,f,g)=>g,J:()=>0});ub("/dev/null",259);Ma(1280,Pa);Ma(1536,Qa);ub("/dev/tty",1280);ub("/dev/tty1",1536);var a=new Uint8Array(1024),b=0,c=()=>{0===b&&(Ha(a),b=a.byteLength);return a[--b]};V("/dev","random",c);V("/dev","urandom",c);U("/dev/shm");U("/dev/shm/tmp")})();
(function(){U("/proc");var a=U("/proc/self");U("/proc/self/fd");rb({O(){var b=Ua(a,"fd",16895,73);b.B={J:K.B.J};b.C={T(c,d){c=+d;var e=S(c);c={parent:null,O:{oa:"fake"},C:{X:()=>e.path},id:c+1};return c.parent=c},ha(){return Array.from(N.entries()).filter(([,c])=>c).map(([c])=>c.toString())}};return b}},"/proc/self/fd")})();h.FS_createPath=ea;h.FS_createDataFile=Za;h.FS_createPreloadedFile=$a;h.FS_unlink=wb;h.FS_createLazyFile=Bb;h.FS_createDevice=V;K.ka=new J(44);K.ka.stack="<generic error, no stack>";
var Jb={k:function(a){try{var b=S(a);return ob(b).M}catch(c){if("undefined"==typeof W||"ErrnoError"!==c.name)throw c;return-c.G}},f:function(a,b,c){X=c>>>0;try{var d=S(a);switch(b){case 0:var e=Y();if(0>e)break;for(;N[e];)e++;return ob(d,e).M;case 1:case 2:return 0;case 3:return d.flags;case 4:return e=Y(),d.flags|=e,0;case 12:return e=Y(),pa[e+0>>>1>>>0]=2,0;case 13:case 14:return 0}return-28}catch(f){if("undefined"==typeof W||"ErrnoError"!==f.name)throw f;return-f.G}},j:function(a,b,c){X=c>>>0;
try{var d=S(a);switch(b){case 21509:return d.D?0:-59;case 21505:if(!d.D)return-59;if(d.D.P.za){a=[3,28,127,21,4,0,1,0,17,19,26,0,18,15,23,22,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0];var e=Y();C[e>>>2>>>0]=25856;C[e+4>>>2>>>0]=5;C[e+8>>>2>>>0]=191;C[e+12>>>2>>>0]=35387;for(var f=0;32>f;f++)A[e+f+17>>>0]=a[f]||0}return 0;case 21510:case 21511:case 21512:return d.D?0:-59;case 21506:case 21507:case 21508:if(!d.D)return-59;if(d.D.P.Aa)for(e=Y(),a=[],f=0;32>f;f++)a.push(A[e+f+17>>>0]);return 0;case 21519:if(!d.D)return-59;
e=Y();return C[e>>>2>>>0]=0;case 21520:return d.D?-28:-59;case 21531:e=Y();if(!d.B.ya)throw new J(59);return d.B.ya(d,b,e);case 21523:if(!d.D)return-59;d.D.P.Ba&&(f=[24,80],e=Y(),pa[e>>>1>>>0]=f[0],pa[e+2>>>1>>>0]=f[1]);return 0;case 21524:return d.D?0:-59;case 21515:return d.D?0:-59;default:return-28}}catch(g){if("undefined"==typeof W||"ErrnoError"!==g.name)throw g;return-g.G}},g:function(a,b,c,d){b>>>=0;X=d>>>=0;try{b=Cb(b);var e=b;if("/"===e.charAt(0))b=e;else{var f=-100===a?"/":S(a).path;if(0==
e.length)throw new J(44);b=f+"/"+e}var g=d?Y():0;return k(b,c,g).M}catch(l){if("undefined"==typeof W||"ErrnoError"!==l.name)throw l;return-l.G}},m:function(a,b){a>>>=0;b>>>=0;try{a=Cb(a);var c=P(a,{Z:!0}).node;var d=mb(c.C.N)(c);C[b>>>2>>>0]=d.va;C[b+4>>>2>>>0]=d.mode;D[b+8>>>2>>>0]=d.Ea;C[b+12>>>2>>>0]=d.uid;C[b+16>>>2>>>0]=d.wa;C[b+20>>>2>>>0]=d.W;E[b+24>>>3]=BigInt(d.size);C[b+32>>>2>>>0]=4096;C[b+36>>>2>>>0]=d.ta;var e=d.R.getTime(),f=d.I.getTime(),g=d.H.getTime();E[b+40>>>3]=BigInt(Math.floor(e/
1E3));D[b+48>>>2>>>0]=e%1E3*1E6;E[b+56>>>3]=BigInt(Math.floor(f/1E3));D[b+64>>>2>>>0]=f%1E3*1E6;E[b+72>>>3]=BigInt(Math.floor(g/1E3));D[b+80>>>2>>>0]=g%1E3*1E6;E[b+88>>>3]=BigInt(d.xa);return 0}catch(l){if("undefined"==typeof W||"ErrnoError"!==l.name)throw l;return-l.G}},n:function(a,b,c,d,e,f,g){a>>>=0;e=-9007199254740992>e||9007199254740992<e?NaN:Number(e);f>>>=0;g>>>=0;try{if(isNaN(e))return 61;var l=S(d);if(0!==(b&2)&&0===(c&2)&&2!==(l.flags&2097155))throw new J(2);if(1===(l.flags&2097155))throw new J(2);
if(!l.B.U)throw new J(43);if(!a)throw new J(28);var p=l.B.U(l,a,e,b,c);var m=p.pa;C[f>>>2>>>0]=p.ia;D[g>>>2>>>0]=m;return 0}catch(r){if("undefined"==typeof W||"ErrnoError"!==r.name)throw r;return-r.G}},o:function(a,b,c,d,e,f){a>>>=0;b>>>=0;f=-9007199254740992>f||9007199254740992<f?NaN:Number(f);try{var g=S(e);if(c&2){if(32768!==(g.node.mode&61440))throw new J(43);d&2||g.B.ba&&g.B.ba(g,B.slice(a,a+b),f,b,d)}}catch(l){if("undefined"==typeof W||"ErrnoError"!==l.name)throw l;return-l.G}},h:()=>Date.now(),
l:function(a){a>>>=0;var b=B.length;if(4294901760<a)return!1;for(var c=1;4>=c;c*=2){var d=b*(1+.2/c);d=Math.min(d,a+100663296);a:{d=(Math.min(4294901760,65536*Math.ceil(Math.max(a,d)/65536))-z.buffer.byteLength+65535)/65536|0;try{z.grow(d);qa();var e=1;break a}catch(f){}e=void 0}if(e)return!0}return!1},q:function(a,b){a>>>=0;b>>>=0;var c=0;Fb().forEach((d,e)=>{var f=b+c;e=D[a+4*e>>>2>>>0]=f;for(f=0;f<d.length;++f)A[e++>>>0]=d.charCodeAt(f);A[e>>>0]=0;c+=d.length+1});return 0},i:function(a,b){a>>>=
0;b>>>=0;var c=Fb();D[a>>>2>>>0]=c.length;var d=0;c.forEach(e=>d+=e.length+1);D[b>>>2>>>0]=d;return 0},d:Ib,c:function(a){try{var b=S(a);t(b);return 0}catch(c){if("undefined"==typeof W||"ErrnoError"!==c.name)throw c;return c.G}},e:function(a,b,c,d){b>>>=0;c>>>=0;d>>>=0;try{a:{var e=S(a);a=b;for(var f,g=b=0;g<c;g++){var l=D[a>>>2>>>0],p=D[a+4>>>2>>>0];a+=8;var m=e,r=l,q=p,u=f,w=A;if(0>q||0>u)throw new J(28);if(null===m.M)throw new J(8);if(1===(m.flags&2097155))throw new J(8);if(L(m.node.mode))throw new J(31);
if(!m.B.read)throw new J(28);var T="undefined"!=typeof u;if(!T)u=m.position;else if(!m.seekable)throw new J(70);var ca=m.B.read(m,w,r,q,u);T||(m.position+=ca);var fa=ca;if(0>fa){var pb=-1;break a}b+=fa;if(fa<p)break;"undefined"!=typeof f&&(f+=fa)}pb=b}D[d>>>2>>>0]=pb;return 0}catch(Ca){if("undefined"==typeof W||"ErrnoError"!==Ca.name)throw Ca;return Ca.G}},p:function(a,b,c,d){b=-9007199254740992>b||9007199254740992<b?NaN:Number(b);d>>>=0;try{if(isNaN(b))return 61;var e=S(a);yb(e,b,c);E[d>>>3]=BigInt(e.position);
e.fa&&0===b&&0===c&&(e.fa=null);return 0}catch(f){if("undefined"==typeof W||"ErrnoError"!==f.name)throw f;return f.G}},b:function(a,b,c,d){b>>>=0;c>>>=0;d>>>=0;try{a:{var e=S(a);a=b;for(var f,g=b=0;g<c;g++){var l=D[a>>>2>>>0],p=D[a+4>>>2>>>0];a+=8;var m=n(e,A,l,p,f);if(0>m){var r=-1;break a}b+=m;if(m<p)break;"undefined"!=typeof f&&(f+=m)}r=b}D[d>>>2>>>0]=r;return 0}catch(q){if("undefined"==typeof W||"ErrnoError"!==q.name)throw q;return q.G}},a:z},Z=await (async function(){function a(d){Z=
d.exports;Z=Kb();sa("wasm-instantiate");return Z}ra("wasm-instantiate");var b={a:Jb};if(h.instantiateWasm)return new Promise(d=>{h.instantiateWasm(b,(e,f)=>{a(e,f);d(e.exports)})});ta??=h.locateFile?h.locateFile("xmllint.wasm",v):v+"xmllint.wasm";try{var c=await wa(b);return a(c.instance)}catch(d){return ba(d),Promise.reject(d)}}()),Lb=h._main=Z.s,Hb=Z.u,Gb=Z.v,Ra=Z.w,Mb=Z.x;
function Kb(){var a=Z;a=Object.assign({},a);a.w=(b=>(c,d)=>b(c,d)>>>0)(a.w);a.x=(b=>c=>b(c)>>>0)(a.x);a.emscripten_stack_get_current=(b=>()=>b()>>>0)(a.emscripten_stack_get_current);return a}h.addRunDependency=ra;h.removeRunDependency=sa;h.FS_createPreloadedFile=$a;h.FS_unlink=a=>wb(a);h.FS_createPath=ea;h.FS_createDevice=V;h.FS_createDataFile=(a,b,c,d,e,f)=>{Za(a,b,c,d,e,f)};h.FS_createLazyFile=Bb;
function Nb(a=[]){a.unshift(la);var b=a.length,c=Mb(4*(b+1)),d=c;a.forEach(f=>{var g=D,l=d>>>2>>>0,p=ha(f)+1,m=Mb(p);ia(f,B,m,p);g[l]=m;d+=4});D[d>>>2>>>0]=0;try{var e=Lb(b,c);Ib(e,!0)}catch(f){if(!(f instanceof xa||"unwind"==f))throw f;}}
function Ob(a=ka){function b(){h.calledRun=!0;if(!oa){if(!h.noFSInit&&!eb){var c,d;eb=!0;c??=h.stdin;d??=h.stdout;e??=h.stderr;c?V("/dev","stdin",c):vb("/dev/tty","/dev/stdin");d?V("/dev","stdout",null,d):vb("/dev/tty","/dev/stdout");e?V("/dev","stderr",null,e):vb("/dev/tty1","/dev/stderr");k("/dev/stdin",0);k("/dev/stdout",1);k("/dev/stderr",1)}Z.r();fb=!1;aa(h);h.onRuntimeInitialized?.();h.noInitialRun||Nb(a);if(h.postRun)for("function"==typeof h.postRun&&(h.postRun=[h.postRun]);h.postRun.length;){var e=
h.postRun.shift();za.unshift(e)}ya(za)}}if(0<F)G=Ob;else{if(h.preRun)for("function"==typeof h.preRun&&(h.preRun=[h.preRun]);h.preRun.length;)Ba();ya(Aa);0<F?G=Ob:h.setStatus?(h.setStatus("Running..."),setTimeout(()=>{setTimeout(()=>h.setStatus(""),1);b()},1)):b()}}if(h.preInit)for("function"==typeof h.preInit&&(h.preInit=[h.preInit]);0<h.preInit.length;)h.preInit.pop()();Ob();moduleRtn=da;


  return moduleRtn;
}
);
})();
if (typeof exports === 'object' && typeof module === 'object') {
  module.exports = Module;
  // This default export looks redundant, but it allows TS to import this
  // commonjs style module.
  module.exports.default = Module;
} else if (typeof define === 'function' && define['amd'])
  define([], () => Module);
;(function initWorker() {

	// Our own messages are tagged with this key so that both sides of the
	// worker channel can tell them apart from unrelated messages that the
	// runtime might send over the same channel, like the "watch:require"
	// messages Node.js sends when running in watch mode.
	// https://github.com/noppa/xmllint-wasm/issues/37
	const messageKey = 'xmllint-wasm';

	let stdout = '';
	let stderr = '';

	function postToParent(message) {
		message[messageKey] = true;
		postMessage(message);
	}

	function onExit(exitCode) {
		postToParent({
			exitCode,
			stdout,
			stderr,
		});
	};
	function onWorkerMessage(event) {
		var data = event.data;
		if (!data || data[messageKey] !== true) {
			// Not a message from us, ignore it.
			return;
		}
		const wasmMemory = new WebAssembly.Memory({
			initial: data.initialMemory,
			maximum: data.maxMemory
		});

		Module({
			inputFiles: data.inputFiles,
			arguments: data.args,
			// TODO: We could eagerly start sending stdout to the parent thread while
			// waiting for more. Or we could probably use some other, more efficient
			// Emscripten API for output communication in the first place.
			// But this seems to work fine for now, better than pushing the stdout
			// values to an array.
			print(text) {
				stdout += text + '\n';
			},
			printErr(text) {
				stderr += text + '\n';
			},
			onExit,
			onAbort(reason) {
				postToParent({
					exitCode: -1,
					stdout: '',
					stderr: 'WASM Abort: ' + reason,
				});
			},
			wasmMemory,
			locateFile(path) {
				if (path !== 'xmllint.wasm') {
					return path;
				}
				// Fix wasm file path to be relative to the worker file path.
				// This also makes bundlers automatically pick up the wasm file.
				return new URL('./xmllint.wasm', import.meta.url).href;
			}
		});
	}


	addEventListener('message', onWorkerMessage);
})();
