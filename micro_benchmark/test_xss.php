<?php
include("source/functions_external.php");
?>



<div class="body_padded">
	<h1>XP Testbed</h1>
	<h2>Micro Benchmark used for Testing HAXSS</h2>

	<div class="vulnerable_code_area">
		<form action="#" method="GET">
			
			<p><label for="form1">Form 1:</label><br />
			<input type="text" id="form1" name="form1"></p>

			<p><label for="form2">Form 2:</label><br />
			<input type="text" id="form2" name="form2"></p>

			<p><label for="form3">Form 3:</label><br />
			<input type="text" id="form3" name="form3"></p>

			<p><label for="form4">Form 4:</label><br />
			<input type="text" id="form4" name="form4"></p>

			<p><label for="form5">Form 5:</label><br />
			<input type="text" id="form5" name="form5"></p>
			
			<p><label for="form6">Form 6:</label><br />
			<input type="text" id="form6" name="form6"></p>

			<p><label for="form7">Form 7:</label><br />
			<input type="text" id="form7" name="form7"></p>
			
			<p><label for="form8">Form 8:</label><br />
			<input type="text" id="form8" name="form8"></p>

			<p><label for="form9">Form 9:</label><br />
			<input type="text" id="form9" name="form9"></p>

			<p><label for="form10">Form 10:</label><br />
			<input type="text" id="form10" name="form10"></p>


			<button type="submit" name="form" value="submitform">Submit</button>

		<br />
	<?php
	if( isset($_GET['form1']) || isset($_GET['form2']) || isset($_GET['form3']) || isset($_GET['form4']) || isset($_GET['form5']) || isset($_GET['form6']) || isset($_GET['form7']) || isset($_GET['form8'])|| isset($_GET['form9'])|| isset($_GET['form10']))
		{
			$form1_data = xss_check_20($_GET['form1']);
			$form2_data = xss_check_21($_GET['form2']);
			$form3_data = xss_check_22($_GET['form3']);
			$form4_data = xss_check_23($_GET['form4']);
			$form5_data = xss_check_24($_GET['form5']);
			$form6_data = xss_check_15($_GET['form6']);
			$form7_data = xss_check_18($_GET['form7']);
			$form8_data = xss_check_16($_GET['form8']);
			$form9_data = xss_check_11($_GET['form9']);
			$form10_data = xss_check_17($_GET['form10']);

		}
	else
		{
		$form1_data = '';
		$form2_data = '';
		$form3_data = '';
		$form4_data = '';
		$form5_data = '';
		$form6_data = '';
		$form7_data = '';
		$form8_data = '';
		$form9_data = '';
		$form10_data = '';
	}
		?>
		</form>
		<br />
		
		Response 1 (CVE-2020-28919) 5.4 (CVSS 3.x):  
		<?php echo($form1_data) ?><br />
		Response 2 (CVE-2021-24884) 9.6 (CVSS 3.x): 
		<a href="https://example.com" data-frmverify="<?php echo($form2_data) ?>"></a><br /> 
		Response 3 (CVE-2021-35043) 6.1 (CVSS 3.x): 
		<a href="<?php echo($form3_data) ?>"> Vulnerable </a> <br />
		Response 4 (CVE-2019-10062) 6.1 (CVSS 3.x): 
		<?php echo($form4_data) ?> <br /> 
		Response 5 (CVE-2021-22889) 6.1 (CVSS 3.x): <div>
			<input type='checkbox' name='vuln_form' value='<?php echo($form5_data) ?>'>
		</div>
		Response 6: <?php echo($form6_data) ?> <br /> 

		Response 7: <script>eval('<?php echo($form7_data) ?>')</script> <br />


		Response 8:<<?php echo($form8_data) ?>> <br />

        Response 9: <script>var x = '<% <?php echo($form9_data) ?>%>';var d = document.createElement('div');d.innerElement = x;document.body.appendChild(d);</script><br />


        Response 10: <img src='<?php echo($form10_data) ?>'><br/> 	
    </div>
</div>
