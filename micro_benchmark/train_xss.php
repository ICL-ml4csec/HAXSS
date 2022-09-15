<?php
include("source/functions_external.php");
?>



<div class="body_padded">
	<h1>XP Testbed</h1>
	<h2>Micro Benchmark used for Training HAXSS</h2>

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

			<p><label for="form11">Form 11:</label><br />
			<input type="text" id="form11" name="form11"></p>

			<p><label for="form12">Form 12:</label><br />
			<input type="text" id="form12" name="form12"></p>

			<p><label for="form13">Form 13:</label><br />
			<input type="text" id="form13" name="form13"></p>

			<p><label for="form14">Form 14:</label><br />
			<input type="text" id="form14" name="form14"></p>

			<p><label for="form15">Form 15:</label><br />
			<input type="text" id="form15" name="form15"></p>

			<p><label for="form16">Form 16:</label><br />
			<input type="text" id="form16" name="form16"></p>


			<!--<p><label for="form17">Form 17:</label><br />
			<input type="text" id="form17" name="form17"></p>

			<p><label for="form18">Form 18:</label><br />
			<input type="text" id="form18" name="form18"></p>

			<p><label for="form19">Form 19:</label><br />
			<input type="text" id="form19" name="form19"></p>-->

			<p><label for="form20">Form 20:</label><br />
			<input type="text" id="form20" name="form20"></p>





			<button type="submit" name="form" value="submitform">Submit</button>

		<br />
	<?php
	if( isset($_GET['form1']) || isset($_GET['form2']) || isset($_GET['form3']) || isset($_GET['form4']) || isset($_GET['form5']) || isset($_GET['form6']) || isset($_GET['form7']) || isset($_GET['form8'])|| isset($_GET['form9'])|| isset($_GET['form10'])|| isset($_GET['form11'])|| isset($_GET['form12'])|| isset($_GET['form13'])|| isset($_GET['form14'])|| isset($_GET['form15'])|| isset($_GET['form16'])|| isset($_GET['form17'])|| isset($_GET['form18'])|| isset($_GET['form19'])|| isset($_GET['form20'])|| isset($_GET['form21'])|| isset($_GET['form22'])|| isset($_GET['form23'])|| isset($_GET['form24'])|| isset($_GET['form25']))
		{
			$form1_data = xss_check_1($_GET['form1']);
			$form2_data = xss_check_2($_GET['form2']);
			$form3_data = xss_check_3($_GET['form3']);
			$form4_data = xss_check_4($_GET['form4']);
			$form5_data = xss_check_5($_GET['form5']);
			$form6_data = xss_check_6($_GET['form6']);
			$form7_data = xss_check_7($_GET['form7']);
			$form8_data = xss_check_8($_GET['form8']);
			$form9_data = xss_check_9($_GET['form9']);
			$form10_data = xss_check_10($_GET['form10']);
			$form11_data = xss_check_11($_GET['form11']);
			$form12_data = xss_check_10($_GET['form12']);
			$form13_data = xss_check_12($_GET['form13']);
			$form14_data = xss_check_13($_GET['form14']);
			$form15_data = xss_check_14($_GET['form15']);
			$form16_data = xss_check_27($_GET['form16']);
			$form17_data = xss_check_27($_GET['form17']);
			$form18_data = xss_check_27($_GET['form18']);
			$form19_data = xss_check_27($_GET['form19']);
			$form20_data = xss_check_28($_GET['form20']);


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
		$form11_data = '';
		$form12_data = '';
		$form13_data = '';
		$form14_data = '';
		$form15_data = '';
		$form16_data = '';
		$form17_data = '';
		$form18_data = '';
		$form19_data = '';
		$form20_data = '';
	}
		?>
		</form>
		<br />
		
		Response 1: <?php echo($form1_data)?> <br /> 
		Response 2: <?php echo($form2_data) ?> <br />  
		Response 3:<script type="text/javascript">function foo() {a="<?php echo($form3_data) ?>"}</script><br />
		Response 4: <?php echo($form4_data) ?> <br /> 
		Response 5: <!-- <?php echo($form5_data) ?> --> <br />
		Response 6: <script>'<?php echo($form6_data) ?>'</script><br /> 
		Response 7: <script><?php echo($form7_data) ?></script><br />
		Response 8: <!--<?php echo($form8_data) ?> --><br />
		Response 9: <style name='<?php echo($form9_data) ?>'></style><br />
        Response 10: <div onmouseover="x='<?php echo($form10_data) ?>'">this is a thing</div> <br /> 
        Response 11: <style> p {color: "<?php echo($form11_data) ?>"}</style><br /> 
        Response 12: <<?php echo($form12_data) ?>><br />
        Response 13: <div><input type="checkbox" name=<?php echo($form13_data) ?>></div><br /> 
        Response 14: <font size=<?php echo($form14_data) ?>></font><br /> 
        Response 15: <<?php echo($form15_data) ?>><br /> 
        <!--Response 16: <a href='<?php echo($form16_data) ?>'>Vulnerable</a><br /> 
        Response 17: <div onclick=<?php echo($form17_data) ?>>Vulnerable</div><br />--> 
	Response 16:<script type="text/javascript" src=<?php echo($form16_data) ?>></script><br />
        <!--Response 19: <div name="x='<?php echo($form19_data) ?>'">this is a thing</div> <br /> -->
	Response 20:<?php echo($form20_data) ?><br />
	</div>

</div>
