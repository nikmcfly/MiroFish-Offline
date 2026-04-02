#!/usr/bin/perl

# Copyright 2025 Institute of Formal and Applied Linguistics, Faculty of
# Mathematics and Physics, Charles University, Czech Republic.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Converter from the CNEC 2.0 Treex format to the NameTag 3 CoNLL format.
#
# This Perl script converts the legacy Treex format used for the CNEC 2.0
# distribution to the NameTag 3 input CoNLL format.

use strict;
use warnings;
use open qw{:utf8 :std};

my $encoding = "BIO";

our %CLASSES = ('A' => 1, 'C' => 1, 'P' => 1, 'T' => 1,
                'ah' => 1, 'at' => 1, 'az' => 1, 'cb' => 1,
                'cn' => 1, 'cp' => 1, 'cr' => 1, 'cs' => 1,
                'gc' => 1, 'gh' => 1, 'gl' => 1, 'gp' => 1,
                'gq' => 1, 'gr' => 1, 'gs' => 1, 'gt' => 1,
                'gu' => 1, 'g_' => 1, 'ia' => 1, 'ic' => 1,
                'if' => 1, 'io' => 1, 'i_' => 1, 'me' => 1,
                'mi' => 1, 'mn' => 1, 'mr' => 1, 'ms' => 1,
                'mt' => 1, 'na' => 1, 'nb' => 1, 'nc' => 1,
                'ni' => 1, 'nm' => 1, 'no' => 1, 'np' => 1,
                'nq' => 1, 'ns' => 1, 'nr' => 1, 'nw' => 1,
                'n_' => 1, 'oa' => 1, 'oc' => 1, 'oe' => 1,
                'om' => 1, 'op' => 1, 'or' => 1, 'o_' => 1,
                'pb' => 1, 'pc' => 1, 'pd' => 1, 'pf' => 1,
                'pm' => 1, 'pp' => 1, 'ps' => 1, 'p_' => 1,
                'qc' => 1, 'qo' => 1, 'tc' => 1, 'td' => 1,
                'tf' => 1, 'th' => 1, 'ti' => 1, 'tm' => 1,
                'tn' => 1, 'tp' => 1, 'ts' => 1, 'ty' => 1);

my ($inside_M_tree, $inside_N_tree) = (0, 0, 0);
my ($id, $form, $lemma, $tag, $ne_type)  = ("", "", "", "", "");
my @lines;
my @a_rfs;
my %ne_types;
my $entity_beginning = 0; # first entity word
while(<>) {
  chomp;

  $inside_M_tree = 1 if /<a_tree id=/;
  $inside_M_tree = 0 if /<\/a_tree>/;
  $inside_N_tree = 1 if /<n_tree id=/;
  $inside_N_tree = 0 if /<\/n_tree>/;

  # M tree
  if (/<form>(.*)<\/form>/) { $form = $1; }
  if (/<lemma>(.*)<\/lemma>/) { $lemma = $1; }
  if (/<tag>(.*)<\/tag>/) { $tag = $1; }
  if ($inside_M_tree and /LM id=\"(.*)\">/) { $id = $1; }
  if (/<\/LM>/ and $inside_M_tree) {
    push @lines, $id." ".$form." ".$lemma." ".$tag." _";
  }

  # N tree
  if (/<ne_type>(.*)<\/ne_type>/) { $ne_type = $1; }

  # entity beginning
  if ($inside_N_tree and (/<a\.rf>(.*)<\/a.rf>/ or /<LM>(.*)<\/LM>/)) {
        push @a_rfs, $1;
  }

  # entity end
  if (/<\/a\.rf>/) {
    if ($encoding eq "BILOU") {
      if (scalar(@a_rfs) == 1) {
        my $a_rf = $a_rfs[0];
        if (exists $CLASSES{$ne_type}) {
          $ne_types{$a_rf} = exists $ne_types{$a_rf} ? $ne_types{$a_rf}."|U-".$ne_type : "U-".$ne_type;
        }
      }
      else {
        for (my $i = 0; $i < scalar(@a_rfs); $i++) {
          my $a_rf = $a_rfs[$i];
          my $current_ne_type = $ne_type;
          if (exists $CLASSES{$ne_type}) {
            $current_ne_type = "B-".$ne_type if $i == 0;
            $current_ne_type = "L-".$ne_type if $i == scalar(@a_rfs)-1;
            $current_ne_type = "I-".$ne_type if $i > 0 && $i < scalar(@a_rfs)-1;
            $ne_types{$a_rf} = exists $ne_types{$a_rf} ? $ne_types{$a_rf}."|".$current_ne_type : $current_ne_type;
          }
        }
      }
    }
    else { # BIO
      for (my $i = 0; $i < scalar(@a_rfs); $i++) {
        my $a_rf = $a_rfs[$i];
        if (exists $CLASSES{$ne_type}) {
          if ($i == 0) {
            $ne_types{$a_rf} = exists $ne_types{$a_rf} ? $ne_types{$a_rf}."|B-".$ne_type : "B-".$ne_type;
          }
          else {
            $ne_types{$a_rf} = exists $ne_types{$a_rf} ? $ne_types{$a_rf}."|I-".$ne_type : "I-".$ne_type;
          }
        }
        #        else {
        #  print STDERR "Skipping NE type \"$ne_type\".\n"
        #}
      }
    }

    @a_rfs = ();
  }

  # print
  if (/<\/n_tree/) {
    my $prev_raw_type = "O";
    foreach my $line (@lines) {
      my ($id, $form, $lemma, $tag, $chunk) = split / /, $line;
      my $type = (exists $ne_types{$id} ? $ne_types{$id} : "O");

      print join(" ", ($form, $lemma, $tag, "_", $type))."\n";
    }
    print "\n";
    @lines = ();
  }
}
