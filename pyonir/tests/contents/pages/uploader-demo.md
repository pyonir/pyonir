title: File Uploads
menu.group: primary
gallery: 
    name: Uploaded Files
    files: $dir/uploads/*?limit=*&where=is_thumb:true
===
This demonstrates a file uploader plugin.

<form id="file_uploader_demo_form" action="/api/demo-uploads" method="POST" type="media" enctype="multipart/form-data">
		<div class="form-messages row">
			<div class="alert">
				no messages for file_uploader_demo
			</div>
		</div>
		<input type="hidden" name="form_id" value="file_uploader_demo">
		<input type="hidden" name="redirect" value="/uploader-demo">
		<input type="hidden" name="csrf_token" value="">
<div class="form-row" tabindex="0">
<label for="foldername" class="form-label">
    Gallery Folder
</label>
    <input tabindex="0" value="" class="form-input " type="text" id="foldername" placeholder="type gallery name" name="foldername">
</div> 

<div class="form-row" tabindex="0">
	<div id="media-upload" class="row">
  <div id="dropbox">
    <!-- <ul id="imageList" class="debug row"> </ul> -->
  <div id="upload-btn" class="btn">Upload Images
    <input type="file" name="files" multiple="" data-parent="files" data-name=""></div>
  </div>
  <div class="progress-bar"><span class="meter"></span></div>
</div>
</div>

<div class="form-row" tabindex="0">
	<button type="submit" class="btn upload">Upload</button>
</div> 

</form>