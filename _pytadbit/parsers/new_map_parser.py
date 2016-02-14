"""
22 may 2015
"""

from pytadbit.utils.file_handling         import magic_open
from bisect                               import bisect_right as bisect
from pytadbit.mapping.restriction_enzymes import map_re_sites
from warnings                             import warn
import os
from sys import stdout

def parse_map(f_names1, f_names2=None, out_file1=None, out_file2=None,
              genome_seq=None, re_name=None, verbose=False, clean=True,
              **kwargs):
    """
    Parse map files

    Keep a summary of the results into 2 tab-separated files that will contain 6
    columns: read ID, Chromosome, position, strand (either 0 or 1), mapped
    sequence lebgth, position of the closest upstream RE site, position of
    the closest downstream RE site.

    The position of reads mapped on reverse strand will be computed from the end of
    the read (original position + read length - 1)

    :param f_names1: a list of path to sam/bam files corresponding to the
       mapping of read1, can also  be just one file
    :param f_names2: a list of path to sam/bam files corresponding to the
       mapping of read2, can also  be just one file
    :param out_file1: path to outfile tab separated format containing mapped
       read1 information
    :param out_file2: path to outfile tab separated format containing mapped
       read2 information
    :param genome_seq: a dictionary generated by :func:`pyatdbit.parser.genome_parser.parse_fasta`.
       containing the genomic sequence
    :param re_name: name of the restriction enzyme used
    :param True clean: remove temporary files required for indentification of
       multiple-contacts
    """
    # not nice, dirty fix in order to allow this function to only parse
    # one SAM file
    if not out_file1:
        raise Exception('ERROR: out_file1 should be given\n')
    if not re_name:
        raise Exception('ERROR: re_name should be given\n')
    if not genome_seq:
        raise Exception('ERROR: genome_seq should be given\n')
    if (f_names2 and not out_file2) or (not f_names2 and out_file2):
        raise Exception('ERROR: out_file2 AND f_names2 needed\n')

    frag_chunk = kwargs.get('frag_chunk', 100000)
    if verbose:
        print 'Searching and mapping RE sites to the reference genome'
    frags = map_re_sites(re_name, genome_seq, frag_chunk=frag_chunk,
                         verbose=verbose)

    if isinstance(f_names1, str):
        f_names1 = [f_names1]
    if isinstance(f_names2, str):
        f_names2 = [f_names2]
    if f_names2:
        fnames = f_names1, f_names2
        outfiles = out_file1, out_file2
    else:
        fnames = (f_names1,)
        outfiles = (out_file1, )

    # max number of reads per intermediate files for sorting
    max_size = 1000000
    
    windows = {}
    multis  = {}
    for read in range(len(fnames)):
        if verbose:
            print 'Loading read' + str(read + 1)
        windows[read] = {}
        num = 0
        # iteration over reads
        nfile = 0
        tmp_files = []
        reads     = []
        for fnam in fnames[read]:
            try:
                fhandler = magic_open(fnam)
            except IOError:
                warn('WARNING: file "%s" not found\n' % fnam)
                continue
            # get the iteration number of the iterative mapping
            try:
                num = int(fnam.split('.')[-1].split(':')[0])
            except:
                num += 1
            # set read counter
            if verbose:
                print 'loading file: %s' % (fnam)
            # start parsing
            read_count = 0
            try:
                while not False:
                    for _ in xrange(max_size):
                        try:
                            reads.append(read_read(fhandler.next(), frags,
                                                   frag_chunk))
                        except KeyError:
                            # Chromosome not in hash
                            continue
                        read_count += 1
                    nfile += 1
                    write_reads_to_file(reads, outfiles[read], tmp_files, nfile)
            except StopIteration:
                fhandler.close()
                nfile += 1
                write_reads_to_file(reads, outfiles[read], tmp_files, nfile)
            windows[read][num] = read_count
        nfile += 1
        write_reads_to_file(reads, outfiles[read], tmp_files, nfile)

        # we have now sorted temporary files
        # we do merge sort for eah pair
        if verbose:
            stdout.write('Merge sort')
            stdout.flush()
        while len(tmp_files) > 1:
            file1 = tmp_files.pop(0)
            file2 = tmp_files.pop(0)
            if verbose:
                stdout.write('.')
            stdout.flush()
            nfile += 1
            tmp_files.append(merge_sort(file1, file2, outfiles[read], nfile))
        if verbose:
            stdout.write('\n')
        tmp_name = tmp_files[0]
        
        if verbose:
            print 'Getting Multiple contacts'
        reads_fh = open(outfiles[read], 'w')
        ## Also pipe file header
        # chromosome sizes (in order)
        reads_fh.write('# Chromosome lengths (order matters):\n')
        for crm in genome_seq:
            reads_fh.write('# CRM %s\t%d\n' % (crm, len(genome_seq[crm])))
        reads_fh.write('# Mapped\treads count by iteration\n')
        for size in windows[read]:
            reads_fh.write('# MAPPED %d %d\n' % (size, windows[read][size]))

        ## Multicontacts
        tmp_reads_fh = open(tmp_name)
        try:
            read_line = tmp_reads_fh.next()
        except StopIteration:
            raise StopIteration('ERROR!\n Nothing parsed, check input files and'
                                ' chromosome names (in genome.fasta and SAM/MAP'
                                ' files).')
        prev_head = read_line.split('\t', 1)[0]
        prev_head = prev_head.split('~' , 1)[0]
        prev_read = read_line
        multis[read] = 0
        for read_line in tmp_reads_fh:
            head = read_line.split('\t', 1)[0]
            head = head.split('~' , 1)[0]
            if head == prev_head:
                multis[read] += 1
                prev_read =  prev_read.strip() + '|||' + read_line
            else:
                reads_fh.write(prev_read)
                prev_read = read_line
            prev_head = head
        reads_fh.write(prev_read)
        reads_fh.close()
        if clean:
            os.system('rm -rf ' + tmp_name)
    return windows, multis

def write_reads_to_file(reads, outfiles, tmp_files, nfile):
    if not reads: # can be...
        return
    tmp_name = os.path.join(*outfiles.split('/')[:-1] +
                            [('tmp_%03d_' % nfile) + outfiles.split('/')[-1]])
    tmp_name = ('/' * outfiles.startswith('/')) + tmp_name
    tmp_files.append(tmp_name)
    out = open(tmp_name, 'w')
    out.write(''.join(sorted(reads, key=lambda x: x.split('\t', 1)[0].split('~')[0])))
    out.close()
    del(reads[:]) # empty list

def merge_sort(file1, file2, outfiles, nfile):
    tmp_name = os.path.join(*outfiles.split('/')[:-1] +
                            [('tmp_%03d_' % nfile) + outfiles.split('/')[-1]])
    tmp_name = ('/' * outfiles.startswith('/')) + tmp_name
    tmp_file = open(tmp_name, 'w')
    fh1 = open(file1)
    fh2 = open(file2)
    greater = lambda x, y: x.split('\t', 1)[0].split('~')[0] > y.split('\t', 1)[0].split('~')[0]
    read1 = fh1.next()
    read2 = fh2.next()
    while not False:
        if greater(read2, read1):
            tmp_file.write(read1)
            try:
                read1 = fh1.next()
            except StopIteration:
                tmp_file.write(read2)
                break
        else:
            tmp_file.write(read2)
            try:
                read2 = fh2.next()
            except StopIteration:
                tmp_file.write(read1)
                break
    for read in fh1:
        tmp_file.write(read)
    for read in fh2:
        tmp_file.write(read)
    fh1.close()
    fh2.close()
    tmp_file.close()
    os.system('rm -f ' + file1)
    os.system('rm -f ' + file2)
    return tmp_name

def read_read(r, frags, frag_chunk):
    name, seq, _, _, ali = r.split('\t')[:5]
    crm, strand, pos = ali.split(':')[:3]
    positive = strand == '+'
    len_seq  = len(seq)
    if positive:
        pos = int(pos)
    else:
        pos = int(pos) + len_seq - 1 # remove 1 because all inclusive
    frag_piece = frags[crm][pos / frag_chunk]
    idx = bisect(frag_piece, pos)
    try:
        next_re = frag_piece[idx]
    except IndexError:
        # case where part of the read is mapped outside chromosome
        count = 0
        while idx >= len(frag_piece) and count < len_seq:
            pos -= 1
            count += 1
            frag_piece = frags[crm][pos / frag_chunk]
            idx = bisect(frag_piece, pos)
        if count >= len_seq:
            raise Exception('Read mapped mostly outside ' +
                            'chromosome\n')
        next_re = frag_piece[idx]
    prev_re = frag_piece[idx - 1 if idx else 0]
    return ('%s\t%s\t%d\t%d\t%d\t%d\t%d\n' % (
        name, crm, pos, positive, len_seq, prev_re, next_re))
