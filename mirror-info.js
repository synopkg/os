function setup_blocks() {
  all_divs = document.getElementsByTagName("div");
  for (var i = 0; i < all_divs.length; i++) {
    if (all_divs[i].className == "blocklink") {
      all_divs[i].style.display = "inline";
      all_divs[i].addEventListener('click', function() { block_visible( this.id.substr(this.id.indexOf(":")+1) ); });
    }
  }
  var tracebox_mask = document.getElementById("tracebox_mask");
  if (tracebox_mask) {
    var height = Math.max(document.body.scrollHeight, document.body.offsetHeight);
    tracebox_mask.style.height=height+"px";
    tracebox_mask.addEventListener('click', function() { block_visible(visible_block); });
  }
}
function block_visible(id) {
  if (visible_block) {
    t = document.getElementById(visible_block).style.display = "none";
    var tracebox_mask = document.getElementById("tracebox_mask");
    if (tracebox_mask) {
      tracebox_mask.style.display = "none";
    }
    if (visible_block == id) {
      visible_block = 0;
      return;
    }
    visible_block = 0;
  }
  var e = document.getElementById(id);
  if (e) {
     var tracebox_mask = document.getElementById("tracebox_mask");
     if (tracebox_mask) {
       tracebox_mask.style.display = "block";
     }
     dgst = id.substr(id.indexOf("-")+1)
     if (! e.src) {
       e.src="../mirror-traces/"+dgst.substr(0, 2)+"/" + dgst + ".txt";
     }
     e.style.display = "block";
     visible_block = id;
  }
}
var visible_block = 0;
setup_blocks();
