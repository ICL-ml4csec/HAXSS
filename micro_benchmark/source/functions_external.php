<?php

function xss_check_1($data)
{
	//remove any ocurrence of <script with 
	//and thing in between
	$input = preg_replace('/<(.*)s(.*)c(.*)r(.*)i(.*)p(.*)t/i', '', $data);
	return $input;
}


function xss_check_2($data)
{
	//remove ocurrences of <script> from the text
	$input = str_replace('<script>', '', $data);
	//$input = urldecode($input);
	$input = html_entity_decode($input);
	return $input;
}

function xss_check_3($data)
{
	//remove single and double quotes and anything that matches the regex
	$input = preg_replace("/'/", '', $data);
	//$input = preg_replace("/'/", '', $input);
	$input = preg_replace("/<script[^>]*>|<\/script>/", '', $input);
	$input = urldecode($input);

	return $input;
}


function xss_check_4($data)
{
	//URL decodes the payload, replaces ocurrences of < and then decodes anything JSON encoded.
	$input_1 = urldecode($data);
	$input_1 = str_replace("<", "&lt;", $input_1);
	$input = json_decode($input_1);
	if($input != null)
	{
		return $input;
	} else
	{
		return $input_1;
	}
}


function xss_check_5($data)
{
	//remove end html comment then decode anything url encoded
	$input = preg_replace('/-->/', '', $data);
	$input = urldecode($input);
	return $input;
}

function xss_check_6($data)
{
	//escapes a ' delimiter but only once and then places the code in a script block
	$input = urldecode($data);
	$input_1 = addslashes($input);
	return $input_1;
}

function xss_check_7($data)
{
	//removes instances of <script> and then on events
	$input = urldecode($data);
	$input = xss_check_1($input);
	$input = preg_replace('/on(.*)=/i','', $input);
	return $input;
}

function xss_check_8($data)
{
	// html encodes single and double quote marks
	$input = htmlEntities($data, ENT_QUOTES);
	return $data;
}

function xss_check_9($data)
{
	// convert double quotes to html encoding, leave single quote alone then remove script or img tags
	//$input = htmlEntities($data, ENT_QUOTES);	
	$input = preg_replace("/(?i)<(script|img|body|style)[^>]*>|<\/(script|img|body|style)>/", '', $data);
	if (str_starts_with($input, '\'') != False)
	{
		return $input;
	}
	else
	{
		return '';
	}


	return $input;
}

function xss_check_10($data)
{
	// escapes single and double quote marks via backslash escaping 
	$input = preg_replace('/"/', '\\"', $data);
	$input = preg_replace('/\'/', '\\\'', $input);
	return $input;
}


function xss_check_11($data)
{

	//backslash escapes double quotes and then decodes anything URL encoded
	$input = preg_replace('/"/', '\\"', $data);
	$input = urldecode($input);
	return $input;
}




function xss_check_12($data)
{
	//remove single quotes, double quotes and spaces
	$input = preg_replace('/"|\'| /', '', $data);
	return $input;
}


function xss_check_13($data)
{
	// remove script, img, and body tags case sensitive 
	$input = preg_replace("/<(script|img|body|style)[^>]*>|<\/(script|body|style)>/", '', $data);
	$input = preg_replace("/<a/", '', $input);
	return $input;
}




function xss_check_14($data)
{
	// remove script image body tags case insensitive
	$input = preg_replace("/(?i)<(script|img|body)[^>]*>|<\/(script|img|body)>/", '', $data);
	return $input;
}

function xss_check_15($data)
{
	//convert < and > to html entities, then URL decode
	$input = str_replace("<","&lt;", $data);
	$input = str_replace(">","&gt;", $input);
	$input = urldecode($input);
	return $input;
}

function xss_check_16($data)
{
	//html encode < then json decode
	$input_1 = str_replace("<","&lt;", $data);
	$input = json_decode($input_1);
	if($input != null)
	{
		return $input;
	} else
	{
		return $input_1;
	}
}

function xss_check_17($data)
{
	//URL decodes the input and then backslash escapes ', ", \, NULL
	$input = urldecode($data);
	$input_1 = addslashes($input);

	return $input_1;
}

function xss_check_18($data)
{
	//similar to xss_check_4 it ecscapes certain characters and has the output in the <script> tag
	$input = str_replace("<","&lt;", $data);
	$input = str_replace(">","&gt;", $input);

	return $input;
}


function xss_check_19($data)
{
	//remove on attributes
	$input = preg_replace('/on(.*)=/i','', $data);
	return $input;
}

function xss_check_20($data)
{
	//CVE-2020-28919
	$input = preg_replace("/(?i)<(script|body|img|a(?!.href=))[^>]*>/", '', $data);
	return $input;
}

function xss_check_21($data)
{
	//CVE-2021-24884 
	$input = urldecode($data);
	$input = html_entity_decode($input);
	$input = strip_tags($input, '<audio><video><img><button><a>');
	return $input;
}

function xss_check_22($data)
{
	//CVE-2021-35043
	$input = html_entity_decode($data);
	return $input;
}


function xss_check_23($data)
{
	//CVE-2019-10062
	$input = preg_replace("/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/i", '', $data);
	return $input;
}


function xss_check_24($data)
{
	//CVE-2021-22889
	$input = htmlspecialchars($data, ENT_SUBSTITUTE | ENT_HTML401);
	return $input;
}
//add in more if needed 
function xss_check_25($data)
{

	return $input;
}

function xss_check_26($data)
{

	return $input;
}

function xss_check_27($data)
{
	// remove script, img, and body tags case sensitive 
	$input = preg_replace("/<(script|img|body|style|a)[^>]*>|<\/(script|body|style|a)>/i", '', $data);
	$input = strip_tags($input,'<script><img><body><a><style>');
	return $input;
}
function xss_check_28($data)
{
	// remove script, img, and body tags case sensitive 
	if(strpos($data, ' ') !== false){
    		return  " ";
	} else{
		$input = preg_replace("/\%0D|%2F|%0C/i", ' ', $data);
		return $input;
	}
}


?>

